"""Passenger WSGI entry point — shared-hosting deployment (SEOHost.pl etc.).

CloudLinux "Aplikacje internetowe" runs the app via Passenger, which speaks
WSGI. FastAPI is ASGI — the asgiref WsgiToAsgi adapter bridges the two.
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

from asgiref.wsgi import WsgiToAsgi  # noqa: E402
from src.api.main import app  # noqa: E402

application = WsgiToAsgi(app)
