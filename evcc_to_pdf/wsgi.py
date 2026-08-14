"""Production WSGI entry point for EVCC to PDF."""
from app import app, start_background_services

start_background_services()
application = app
