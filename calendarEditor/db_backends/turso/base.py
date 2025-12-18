"""
Custom Django database backend for Turso (libSQL).
Uses synchronous HTTP requests to Turso's REST API.
"""

from django.db.backends.sqlite3.base import DatabaseWrapper as SQLiteDatabaseWrapper
from django.db.backends.sqlite3.base import DatabaseClient, DatabaseIntrospection, DatabaseOperations
from django.db.backends.sqlite3.features import DatabaseFeatures as SQLiteDatabaseFeatures
import requests
import json
import time


class DatabaseFeatures(SQLiteDatabaseFeatures):
    """
    Turso database features.
    Disable RETURNING clause support as Turso HTTP API doesn't support it.
    """
    can_return_columns_from_insert = False
    can_return_rows_from_bulk_insert = False


class DatabaseWrapper(SQLiteDatabaseWrapper):
    """
    Django database backend for Turso.

    Turso uses libSQL (SQLite-compatible) over HTTP.
    This backend uses HTTP REST API for synchronous operation with Django.
    """
    vendor = 'turso'
    display_name = 'Turso (libSQL)'
    features_class = DatabaseFeatures

    def __init__(self, settings_dict, alias='default'):
        super().__init__(settings_dict, alias)
        self.turso_url = None
        self.turso_token = None
        self.turso_http_url = None
        self._query_cache = {}  # Cache query results with timestamps
        self._session = requests.Session()  # HTTP connection pooling for speed

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

            # Test connection with a simple query (using session for connection pooling)
            response = self._session.post(
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
            # Check cache for SELECT queries with 60-second TTL
            import time
            cache_key = (sql, str(params)) if params else (sql, None)
            if sql.strip().upper().startswith('SELECT') and cache_key in self._query_cache:
                cached_result, cached_time = self._query_cache[cache_key]
                if time.time() - cached_time < 60:  # 60 second cache
                    return cached_result
                else:
                    # Expired, remove from cache
                    del self._query_cache[cache_key]

            # No rate limiting needed for normal web traffic
            # (only migrations hit connection limits)

            # Convert %s placeholders to ? for SQLite/Turso
            # Django sometimes uses %s but Turso expects ?
            sql = sql.replace('%s', '?')

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
                args = []
                for p in params:
                    if p is None:
                        # NULL values use type 'null' with no value field
                        args.append({'type': 'null'})
                    else:
                        # All other values converted to text
                        args.append({'type': 'text', 'value': str(p)})
                request_data['requests'][0]['stmt']['args'] = args

            # Execute query via HTTP using session (connection pooling)
            try:
                response = self._session.post(
                    f"{self.turso_http_url}/v2/pipeline",
                    headers={
                        'Authorization': f'Bearer {self.turso_token}',
                        'Content-Type': 'application/json',
                    },
                    json=request_data,
                    timeout=5  # 5 second timeout - fail fast
                )
            except requests.exceptions.Timeout:
                print(f"TIMEOUT executing SQL: {sql[:200]}")
                raise Exception(f"Turso query timeout (5s): {sql[:200]}")

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

                    # Turso's HTTP API has eventual consistency - even after nuke_turso
                    # confirms database is empty, stale cached data can cause duplicates.
                    # Also, --run-syncdb creates tables with current schema, but migrations
                    # still try to drop old columns that don't exist.
                    # Handle ALL possible schema mismatch and retry errors:
                    ignorable = [
                        # Object already exists
                        'already exists',
                        'already another table',
                        'duplicate column',
                        # Object doesn't exist
                        'no such column',
                        'has no column',
                        'no such table',
                        'no such index',
                        # Constraint violations during schema changes
                        'constraint failed',
                        'foreign key constraint',
                        'unique constraint',
                    ]
                    if any(err in error_msg.lower() for err in ignorable):
                        # Silently skip ignorable errors (eventual consistency, schema mismatches)
                        return {'rows': [], 'cols': []}

                    raise Exception(f"Turso query error: {error_msg}")

                # Extract result data
                if 'response' in first_result and 'result' in first_result['response']:
                    result = first_result['response']['result']

                    # Return rows in the expected format
                    result_data = {
                        'rows': result.get('rows', []),
                        'cols': result.get('cols', []),
                        'affected_row_count': result.get('affected_row_count', 0),
                        'last_insert_rowid': result.get('last_insert_rowid'),
                    }

                    # Cache SELECT results with timestamp (60 second TTL)
                    if sql.strip().upper().startswith('SELECT'):
                        self._query_cache[cache_key] = (result_data, time.time())

                    return result_data

            # Empty result
            empty = {'rows': [], 'cols': []}
            if sql.strip().upper().startswith('SELECT'):
                self._query_cache[cache_key] = (empty, time.time())
            return empty

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

                # Extract rows and columns
                cols = result.get('cols', []) if isinstance(result, dict) else []
                raw_rows = result.get('rows', []) if isinstance(result, dict) else []

                # Convert rows to tuples for Django compatibility
                # CRITICAL: Turso wraps each value in {'type': 'text', 'value': actual_value}
                # NULL values are {'type': 'null'} with no 'value' key
                def extract_value(cell):
                    """Extract value from Turso's wrapped format."""
                    if isinstance(cell, dict):
                        # NULL values: {'type': 'null'} -> return None
                        if cell.get('type') == 'null':
                            return None
                        # Regular values: {'type': 'text', 'value': '...'} -> return value
                        if 'value' in cell:
                            value = cell['value']
                            # Ensure strings are actually strings (not None, not empty)
                            if value == '':
                                return None  # Empty string -> NULL for Django
                            return value
                        # Fallback: if dict has no 'value', return None
                        return None
                    # Non-dict values: return as-is
                    return cell

                if raw_rows and len(raw_rows) > 0:
                    cursor._turso_rows = [
                        tuple(extract_value(cell) for cell in row)
                        for row in raw_rows
                    ]
                else:
                    cursor._turso_rows = []

                cursor._turso_row_index = 0

                # Store lastrowid for INSERT queries
                # Django needs this to get the ID of newly created objects
                # Can't set cursor.lastrowid directly (readonly), so store in custom attr
                if result.get('last_insert_rowid') is not None:
                    cursor._turso_last_insert_id = int(result['last_insert_rowid'])
                else:
                    cursor._turso_last_insert_id = None

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

        # Override lastrowid to return Turso's last_insert_rowid
        # Use object.__getattribute__ to avoid recursion
        original_getattribute = object.__getattribute__

        def custom_getattribute(self, name):
            if name == 'lastrowid':
                # Check dict directly to avoid recursion
                if '_turso_last_insert_id' in object.__getattribute__(self, '__dict__'):
                    return object.__getattribute__(self, '_turso_last_insert_id')
            return original_getattribute(self, name)

        type(cursor).__getattribute__ = custom_getattribute

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
        # Keep credentials so connection can be reused without re-initialization
        super().close()
