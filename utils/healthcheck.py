"""
Healthcheck HTTP server for Docker container monitoring.

Provides a simple HTTP endpoint that returns 200 OK if the bot is running.
Used by Docker healthcheck to verify container health.
"""

import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger(__name__)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """
    Simple HTTP handler for healthcheck requests.

    Returns 200 OK for GET requests to any path.
    """

    def do_GET(self):
        """Handle GET requests."""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        """Suppress default HTTP logging to avoid log spam."""
        pass


class HealthCheckServer:
    """
    HTTP server for Docker healthcheck.

    Runs in a separate daemon thread and doesn't interfere with bot operation.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        """
        Initialize healthcheck server.

        Args:
            host: Host to bind to (default: 0.0.0.0 for Docker)
            port: Port to listen on (default: 8080)
        """
        self.host = host
        self.port = port
        self.server = None
        self._thread = None

    def start(self) -> None:
        """Start the healthcheck server in a background thread."""
        try:
            self.server = HTTPServer((self.host, self.port), HealthCheckHandler)

            self._thread = threading.Thread(
                target=self.server.serve_forever, name="HealthCheckServer", daemon=True
            )
            self._thread.start()

            logger.info(f"✅ Healthcheck server started on {self.host}:{self.port}")

        except Exception as e:
            logger.error(f"❌ Failed to start healthcheck server: {e}")

    def stop(self) -> None:
        """Stop the healthcheck server gracefully."""
        if self.server:
            try:
                self.server.shutdown()
                logger.info("🛑 Healthcheck server stopped")
            except Exception as e:
                logger.error(f"❌ Error stopping healthcheck server: {e}")
