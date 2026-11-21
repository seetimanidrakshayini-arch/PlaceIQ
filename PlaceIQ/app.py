"""PlaceIQ – Flask application entry point.

Run:  python app.py        (development)
      gunicorn app:app     (production, Linux/macOS)
"""
import os
from flask import Flask, jsonify, send_from_directory
from werkzeug.exceptions import HTTPException

from config import Config, BASE_DIR
import db
from routes import auth, student, officer

STATIC_DIR = os.path.join(BASE_DIR, "static")


def create_app():
    app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
    app.config.from_object(Config)
    if Config.SECRET_KEY in ("", "dev-only-insecure-key", "change-this-to-a-long-random-string") and not Config.DEBUG:
        print("WARNING: set a strong SECRET_KEY in .env before deploying.")
    app.teardown_appcontext(db.close_db)

    app.register_blueprint(auth.bp)
    app.register_blueprint(student.bp)
    app.register_blueprint(officer.bp)

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/api/departments")
    def departments():
        rows = db.query("SELECT name FROM departments ORDER BY name")
        return jsonify({"ok": True, "items": [r["name"] for r in rows]})

    @app.get("/api/health")
    def health():
        try:
            db.query("SELECT 1 x")
            return jsonify({"ok": True, "db": "connected"})
        except Exception as e:  # noqa
            return jsonify({"ok": False, "db": "error", "error": str(e)}), 500

    @app.errorhandler(HTTPException)
    def http_error(e):
        if e.code == 413:
            return jsonify({"ok": False, "error": "File too large (max %d MB)." % Config.MAX_RESUME_MB}), 413
        return jsonify({"ok": False, "error": e.description}), e.code

    @app.errorhandler(Exception)
    def unhandled(e):
        app.logger.exception("Unhandled error")
        return jsonify({"ok": False, "error": "Server error. Check the terminal log."}), 500

    @app.after_request
    def headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        if resp.mimetype in ("application/json",):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=Config.PORT, debug=Config.DEBUG)
