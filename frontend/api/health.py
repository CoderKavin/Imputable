"""Health check endpoint."""

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "version": "1.0.0",
        "runtime": "vercel-python"
    })


handler = app
