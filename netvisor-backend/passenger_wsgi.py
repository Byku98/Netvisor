"""Passenger WSGI entry point — shared-hosting deployment (SEOHost.pl etc.).

Passenger/lswsgi speaks WSGI; FastAPI is ASGI. The a2wsgi ASGIToWSGI adapter
bridges the two (asgiref's WsgiToAsgi is the wrong direction — it adapts WSGI
apps INTO ASGI servers).

Our API is plain request/response (no websockets), so the bridge is cheap.

Passenger config (DirectAdmin UI):
    Plik startowy aplikacji:  passenger_wsgi.py
    Punkt wejścia aplikacji:  application
"""

import sys
from pathlib import Path

# Ensure the backend root (this file's directory) is importable — Passenger
# does not always put the app root on sys.path.
APP_ROOT = Path(__file__).resolve().parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from a2wsgi.asgi import ASGIMiddleware  # noqa: E402
from src.api.main import app  # noqa: E402

application = ASGIMiddleware(app)
