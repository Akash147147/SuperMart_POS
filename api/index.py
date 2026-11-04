"""Vercel Serverless WSGI entry point for SuperMart POS."""
import os
import sys
from pathlib import Path

# Add project root directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app, init_database

# Create production Flask instance
app = create_app('production')

# Auto-initialize database tables and default admin/cashier accounts
with app.app_context():
    try:
        init_database(app)
    except Exception as e:
        app.logger.warning(f"Database initialization: {e}")
