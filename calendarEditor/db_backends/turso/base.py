"""
Custom Django database backend for Turso (libSQL).
Wraps libsql_client to work with Django's ORM.
"""

from django.db.backends.sqlite3.base import DatabaseWrapper as SQLiteDatabaseWrapper
from django.db.backends.sqlite3.base import DatabaseClient, DatabaseIntrospection, DatabaseOperations
import libsql_client


class DatabaseWrapper(SQLiteDatabaseWrapper):
    """
    Django database backend for Turso.

    Turso uses libSQL (SQLite-compatible) over HTTP/WebSockets.
    This backend uses libsql_client to connect to Turso instead of local SQLite.
    """
    vendor = 'turso'
    display_name = 'Turso (libSQL)'

    def __init__(self, settings_dict, alias='default'):
        super().__init__(settings_dict, alias)
        self.turso_client = None

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

        return {
            'url': turso_url,
            'auth_token': turso_token,
        }

    def get_new_connection(self, conn_params):
        """Create connection to Turso using libsql_client."""
        try:
            self.turso_client = libsql_client.create_client(
                url=conn_params['url'],
                auth_token=conn_params['auth_token']
            )

            print(f"✅ Connected to Turso: {conn_params['url']}")

            # Create an in-memory SQLite connection for Django's ORM
            # We'll intercept execute() to send queries to Turso instead
            conn = super().get_new_connection({
                'database': ':memory:',
                'check_same_thread': False,
            })

            return conn

        except Exception as e:
            raise ConnectionError(f"Failed to connect to Turso: {e}")

    def _execute_turso_query(self, sql, params=None):
        """Execute query against Turso using libsql_client."""
        try:
            # Convert Django query params to Turso format
            if params:
                # libsql_client expects params as a list
                result = self.turso_client.execute(sql, list(params))
            else:
                result = self.turso_client.execute(sql)

            return result

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
        if self.turso_client:
            try:
                self.turso_client.close()
            except:
                pass
            self.turso_client = None
        super().close()
