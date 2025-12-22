"""Debug endpoint to check what's working"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        result = {
            "python_version": sys.version,
            "env_vars": {
                "DATABASE_URL": "set" if os.environ.get("DATABASE_URL") else "NOT SET",
                "FIREBASE_PROJECT_ID": os.environ.get("FIREBASE_PROJECT_ID", "NOT SET"),
                "FIREBASE_CLIENT_EMAIL": "set" if os.environ.get("FIREBASE_CLIENT_EMAIL") else "NOT SET",
                "FIREBASE_PRIVATE_KEY": "set" if os.environ.get("FIREBASE_PRIVATE_KEY") else "NOT SET",
            },
            "imports": {}
        }

        # Test imports
        try:
            import sqlalchemy
            result["imports"]["sqlalchemy"] = sqlalchemy.__version__
        except Exception as e:
            result["imports"]["sqlalchemy"] = f"FAILED: {e}"

        try:
            import psycopg2
            result["imports"]["psycopg2"] = psycopg2.__version__
        except Exception as e:
            result["imports"]["psycopg2"] = f"FAILED: {e}"

        try:
            import firebase_admin
            result["imports"]["firebase_admin"] = firebase_admin.__version__
        except Exception as e:
            result["imports"]["firebase_admin"] = f"FAILED: {e}"

        # Test DB connection
        try:
            from sqlalchemy import create_engine, text
            db_url = os.environ.get("DATABASE_URL", "")
            if db_url:
                engine = create_engine(db_url, connect_args={"sslmode": "require"})
                with engine.connect() as conn:
                    r = conn.execute(text("SELECT 1"))
                    result["db_connection"] = "SUCCESS"
            else:
                result["db_connection"] = "NO DATABASE_URL"
        except Exception as e:
            result["db_connection"] = f"FAILED: {e}"

        # Test Firebase init
        try:
            import firebase_admin
            from firebase_admin import credentials

            project_id = os.environ.get("FIREBASE_PROJECT_ID")
            client_email = os.environ.get("FIREBASE_CLIENT_EMAIL")
            private_key = os.environ.get("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n")

            if all([project_id, client_email, private_key]):
                try:
                    app = firebase_admin.get_app()
                    result["firebase_init"] = "ALREADY INITIALIZED"
                except ValueError:
                    cred = credentials.Certificate({
                        "type": "service_account",
                        "project_id": project_id,
                        "private_key": private_key,
                        "client_email": client_email,
                        "token_uri": "https://oauth2.googleapis.com/token",
                    })
                    firebase_admin.initialize_app(cred)
                    result["firebase_init"] = "SUCCESS"
            else:
                result["firebase_init"] = "MISSING CREDENTIALS"
        except Exception as e:
            result["firebase_init"] = f"FAILED: {e}"

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(result, indent=2).encode())
