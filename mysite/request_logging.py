"""
Custom middleware to control request logging.
"""
import time


class RequestLoggingMiddleware:
    """
    Middleware to log HTTP requests with timing info.
    Only logs errors and POST requests - silences successful GETs.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - start_time

        # Get IP address
        ip_address = self._get_client_ip(request)

        # Only log non-200 status codes, POST requests, and WebSocket upgrades
        should_log = (
            response.status_code != 200 or
            request.method == 'POST' or
            request.META.get('HTTP_UPGRADE', '').lower() == 'websocket'
        )

        if should_log:
            print(f"HTTP {request.method} {request.path} {response.status_code} [{duration:.2f}, {ip_address}]")

        return response

    def _get_client_ip(self, request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'Unknown')
        return ip
