"""
Custom Django database backend for Turso (libSQL).
Uses synchronous HTTP requests to Turso's REST API.
"""

from django.db.backends.sqlite3.base import DatabaseWrapper as SQLiteDatabaseWrapper
from django.db.backends.sqlite3.base import DatabaseClient, DatabaseIntrospection, DatabaseOperations
import requests
import json


class DatabaseWrapper(SQLiteDatabaseWrapper):
    """
    Django database backend for Turso.

    Turso uses libSQL (SQLite-compatible) over HTTP.
    This backend uses HTTP REST API for synchronous operation with Django.
    """
    vendor = 'turso'
    display_name = 'Turso (libSQL)'

    def __init__(self, settings_dict, alias='default'):
        super().__init__(settings_dict, alias)
        self.turso_url = None
        self.turso_token = None
        self.turso_http_url = None

    def get_connection_params(self):
        """Get Turso connection parameters from settings."""
        settings = self.settings_dict

        # Extract Turso credentials
        turso_url = settings.get('TURSO_URL')
        turso_token = settings.get('TURSO_TOKEN')

        if not turso_url or not turso_token:
            raise ValueError(
                "Turso database requires TURSO_URL and TURSO_TOKEN in DATABASES settings.\n"
                "Example:\n"
                "DATABASES = {\n"
                "    'default': {\n"
                "        'ENGINE': 'calendarEditor.db_backends.turso',\n"
                "        'TURSO_URL': 'libsql://your-db.turso.io',\n"
                "        'TURSO_TOKEN': 'your-token',\n"
                "    }\n"
                "}"
            )

        # Convert libsql:// URL to https:// for HTTP API
        # libsql://your-db.turso.io → https://your-db.turso.io
        http_url = turso_url.replace('libsql://', 'https://')

        return {
            'url': turso_url,
            'auth_token': turso_token,
            'http_url': http_url,
        }

    def get_new_connection(self, conn_params):
        """Create connection to Turso using HTTP API."""
        try:
            self.turso_url = conn_params['url']
            self.turso_token = conn_params['auth_token']
            self.turso_http_url = conn_params['http_url']

            # Test connection with a simple query
            response = requests.post(
                f"{self.turso_http_url}/v2/pipeline",
                headers={
                    'Authorization': f'Bearer {self.turso_token}',
                    'Content-Type': 'application/json',
                },
                json={
                    'requests': [
                        {'type': 'execute', 'stmt': {'sql': 'SELECT 1'}}
                    ]
                },
                timeout=10
            )

            if response.status_code != 200:
                raise ConnectionError(
                    f"Turso connection test failed: {response.status_code}\n"
                    f"Response: {response.text}"
                )

            print(f"✅ Connected to Turso via HTTP: {self.turso_url}")

            # Create an in-memory SQLite connection for Django's ORM
            # We'll intercept execute() to send queries to Turso instead
            conn = super().get_new_connection({
                'database': ':memory:',
                'check_same_thread': False,
            })

            return conn

        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to connect to Turso: {e}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Turso: {e}")

    def _execute_turso_query(self, sql, params=None):
        """Execute query against Turso using HTTP API."""
        try:
            # Prepare request payload
            request_data = {
                'requests': [
                    {
                        'type': 'execute',
                        'stmt': {
                            'sql': sql,
                        }
                    }
                ]
            }

            # Add parameters if provided
            if params:
                request_data['requests'][0]['stmt']['args'] = [
                    {'type': 'text', 'value': str(p) if p is not None else None}
                    for p in params
                ]

            # Execute query via HTTP
            response = requests.post(
                f"{self.turso_http_url}/v2/pipeline",
                headers={
                    'Authorization': f'Bearer {self.turso_token}',
                    'Content-Type': 'application/json',
                },
                json=request_data,
                timeout=30
            )

            if response.status_code != 200:
                raise Exception(
                    f"Query failed with status {response.status_code}: {response.text}"
                )

            # Parse response
            result_data = response.json()

            # Turso v2 pipeline response format:
            # {
            #   "results": [
            #     {
            #       "type": "ok",
            #       "response": {
            #         "type": "execute",
            #         "result": {
            #           "cols": ["column1", "column2"],
            #           "rows": [[value1, value2], ...],
            #           "affected_row_count": N,
            #           "last_insert_rowid": N
            #         }
            #       }
            #     }
            #   ]
            # }

            if 'results' in result_data and len(result_data['results']) > 0:
                first_result = result_data['results'][0]

                # Check if query succeeded
                if first_result.get('type') == 'error':
                    error_msg = first_result.get('error', {}).get('message', 'Unknown error')
                    raise Exception(f"Turso query error: {error_msg}")

                # Extract result data
                if 'response' in first_result and 'result' in first_result['response']:
                    result = first_result['response']['result']

                    # Return rows in the expected format
                    return {
                        'rows': result.get('rows', []),
                        'cols': result.get('cols', []),
                        'affected_row_count': result.get('affected_row_count', 0),
                        'last_insert_rowid': result.get('last_insert_rowid'),
                    }

            # Empty result
            return {'rows': [], 'cols': []}

        except requests.exceptions.RequestException as e:
            raise Exception(f"Turso HTTP request failed: {e}\nSQL: {sql}\nParams: {params}")
        except Exception as e:
            raise Exception(f"Turso query failed: {e}\nSQL: {sql}\nParams: {params}")

    def create_cursor(self, name=None):
        """Create a cursor that executes queries against Turso."""
        cursor = super().create_cursor(name)

        # Store reference to parent wrapper
        cursor._turso_wrapper = self

        # Wrap cursor to intercept execute() calls
        original_execute = cursor.execute

        def turso_execute(sql, params=None):
            # Send ALL queries to Turso (including PRAGMAs and introspection)
            try:
                result = self._execute_turso_query(sql, params)

                # Store result and prepare for fetch operations
                cursor._turso_result = result

                # Convert rows to tuples for Django compatibility
                # Turso can return rows as dicts OR arrays - handle both
                cols = result.get('cols', []) if isinstance(result, dict) else []
                raw_rows = result.get('rows', []) if isinstance(result, dict) else []

                if raw_rows and len(raw_rows) > 0:
                    first_row = raw_rows[0]
                    if isinstance(first_row, dict):
                        # Rows are dicts - convert to tuples using column order
                        cursor._turso_rows = [
                            tuple(row.get(col) for col in cols)
                            for row in raw_rows
                        ]
                    else:
                        # Rows are arrays - convert to tuples
                        cursor._turso_rows = [
                            tuple(row) if isinstance(row, (list, tuple)) else row
                            for row in raw_rows
                        ]
                else:
                    cursor._turso_rows = []

                cursor._turso_row_index = 0

                return cursor
            except Exception as e:
                # For errors, provide helpful context
                raise Exception(f"Turso query failed: {e}\nSQL: {sql}")

        cursor.execute = turso_execute

        # Override fetchone to return one row at a time
        original_fetchone = cursor.fetchone

        def turso_fetchone():
            if hasattr(cursor, '_turso_rows'):
                if cursor._turso_row_index < len(cursor._turso_rows):
                    row = cursor._turso_rows[cursor._turso_row_index]
                    cursor._turso_row_index += 1
                    return row  # Already a tuple
                return None
            return original_fetchone()

        cursor.fetchone = turso_fetchone

        # Override fetchall to return all rows
        original_fetchall = cursor.fetchall

        def turso_fetchall():
            if hasattr(cursor, '_turso_rows'):
                rows = cursor._turso_rows[cursor._turso_row_index:]
                cursor._turso_row_index = len(cursor._turso_rows)
                return rows  # Already tuples
            return original_fetchall()

        cursor.fetchall = turso_fetchall

        # Override fetchmany to return N rows
        original_fetchmany = cursor.fetchmany

        def turso_fetchmany(size=cursor.arraysize):
            if hasattr(cursor, '_turso_rows'):
                end_index = min(cursor._turso_row_index + size, len(cursor._turso_rows))
                rows = cursor._turso_rows[cursor._turso_row_index:end_index]
                cursor._turso_row_index = end_index
                return rows  # Already tuples
            return original_fetchmany(size)

        cursor.fetchmany = turso_fetchmany

        return cursor

    def disable_constraint_checking(self):
        """
        Disable foreign key constraint checking.
        Required for Django migrations to work with SQLite schema editor.
        """
        with self.cursor() as cursor:
            cursor.execute('PRAGMA foreign_keys = OFF')
        return True

    def enable_constraint_checking(self):
        """
        Re-enable foreign key constraint checking after migrations.
        """
        self.check_constraints()
        with self.cursor() as cursor:
            cursor.execute('PRAGMA foreign_keys = ON')

    def check_constraints(self, table_names=None):
        """
        Check that all foreign key constraints are valid.
        This is a no-op for Turso since it validates constraints on write.
        """
        pass

    def close(self):
        """Close Turso connection."""
        # HTTP connections are stateless, nothing to close
        self.turso_url = None
        self.turso_token = None
        self.turso_http_url = None
        super().close()
