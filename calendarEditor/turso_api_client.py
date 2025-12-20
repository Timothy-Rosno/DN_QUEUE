"""Client for Turso Platform API to fetch usage metrics."""
import os
import requests


class TursoAPIClient:
    """Client for interacting with Turso Platform API."""

    def __init__(self):
        self.org_slug = os.environ.get('TURSO_ORG_SLUG')
        self.api_token = os.environ.get('TURSO_API_TOKEN') or os.environ.get('TURSO_AUTH_TOKEN')
        self.base_url = "https://api.turso.tech"

    def get_usage_metrics(self):
        """
        Fetch organization usage metrics from Turso API.

        Returns:
            dict: Usage metrics including rows_read, rows_written, storage_bytes
                  Returns None if API call fails or credentials missing
        """
        if not self.org_slug or not self.api_token:
            print(f"Turso API: Missing credentials - org_slug={self.org_slug}, api_token={'set' if self.api_token else 'missing'}")
            return None

        try:
            url = f"{self.base_url}/v1/organizations/{self.org_slug}/usage"
            headers = {"Authorization": f"Bearer {self.api_token}"}
            print(f"Turso API: Fetching from {url}")
            response = requests.get(url, headers=headers, timeout=10)

            print(f"Turso API: Response status {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                usage = data.get('organization', {}).get('usage', {})
                return {
                    'rows_read': usage.get('rows_read', 0),
                    'rows_written': usage.get('rows_written', 0),
                    'storage_bytes': usage.get('storage_bytes', 0),
                    'databases': len(data.get('organization', {}).get('databases', [])),
                }
            else:
                print(f"Turso API: Error response: {response.text}")
            return None
        except Exception as e:
            print(f"Turso API error: {e}")
            import traceback
            traceback.print_exc()
            return None
