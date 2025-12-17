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

            # Extract results from response
            if 'results' in result_data and len(result_data['results']) > 0:
                result = result_data['results'][0]
                if 'response' in result and 'result' in result['response']:
                    return result['response']['result']

            return {'rows': []}

        except requests.exceptions.RequestException as e:
            raise Exception(f"Turso HTTP request failed: {e}\nSQL: {sql}\nParams: {params}")
        except Exception as e:
            raise Exception(f"Turso query failed: {e}\nSQL: {sql}\nParams: {params}")

    def create_cursor(self, name=None):
        """Create a cursor that executes queries against Turso."""
        cursor = super().create_cursor(name)

        # Wrap cursor to intercept execute() calls
        original_execute = cursor.execute

        def turso_execute(sql, params=None):
            # Send query to Turso instead of local SQLite
            try:
                result = self._execute_turso_query(sql, params)
                # Store result for fetchall()
                cursor._turso_result = result
                return cursor
            except Exception as e:
                # Fall back to local execution for some queries (like introspection)
                if 'sqlite_master' in sql or 'pragma' in sql.lower():
                    return original_execute(sql, params)
                raise e

        cursor.execute = turso_execute

        # Override fetchall to return Turso results
        original_fetchall = cursor.fetchall

        def turso_fetchall():
            if hasattr(cursor, '_turso_result'):
                result = cursor._turso_result
                if hasattr(result, 'rows'):
                    return result.rows
                return []
            return original_fetchall()

        cursor.fetchall = turso_fetchall

        return cursor

    def close(self):
        """Close Turso connection."""
        # HTTP connections are stateless, nothing to close
        self.turso_url = None
        self.turso_token = None
        self.turso_http_url = None
        super().close()
