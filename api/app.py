
"""Простой REST API: Flask + MongoDB + Redis.

Эндпоинты:
    GET  /api/health  - состояние сервиса и зависимостей (200 или 503)
    GET  /api/visits  - счётчик посещений в Redis (увеличивается на 1)
    GET  /api/items   - последние 50 записей из MongoDB
    POST /api/items   - добавить запись {"name": "..."}
"""
import os
from urllib.parse import quote_plus

import redis
from flask import Flask, jsonify, request
from pymongo import MongoClient

DB_NAME = "appdb"
COLLECTION = "items"
MAX_NAME_LEN = 100


def read_secret(file_var, plain_var, default=""):
    """Читает значение из файла (Docker secret) или из обычной переменной."""
    path = os.environ.get(file_var)
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    return os.environ.get(plain_var, default)


def build_mongo_client():
    user = quote_plus(os.environ.get("MONGO_USER", "admin"))
    password = quote_plus(read_secret("MONGO_PASSWORD_FILE", "MONGO_PASSWORD"))
    host = os.environ.get("MONGO_HOST", "mongodb")
    port = os.environ.get("MONGO_PORT", "27017")
    uri = "mongodb://{}:{}@{}:{}/?authSource=admin".format(user, password, host, port)
    return MongoClient(uri, serverSelectionTimeoutMS=2000)


def build_redis_client():
    url = os.environ.get("REDIS_URL", "redis://redis:6379")
    return redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)


def create_app(mongo=None, cache=None):
    """Фабрика приложения. Клиенты можно подменить (удобно для тестов)."""
    app = Flask(__name__)
    clients = {"mongo": mongo, "cache": cache}

    def get_mongo():
        if clients["mongo"] is None:
            clients["mongo"] = build_mongo_client()
        return clients["mongo"]

    def get_cache():
        if clients["cache"] is None:
            clients["cache"] = build_redis_client()
        return clients["cache"]

    @app.get("/api/health")
    def health():
        status = {"api": "ok"}
        try:
            get_mongo().admin.command("ping")
            status["mongodb"] = "ok"
        except Exception as exc:  # noqa: BLE001
            status["mongodb"] = "error: {}".format(type(exc).__name__)
        try:
            get_cache().ping()
            status["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            status["redis"] = "error: {}".format(type(exc).__name__)
        healthy = all(v == "ok" for v in status.values())
        return jsonify(status), (200 if healthy else 503)

    @app.get("/api/visits")
    def visits():
        try:
            count = get_cache().incr("visits")
        except Exception:  # noqa: BLE001
            return jsonify(error="redis unavailable"), 503
        return jsonify(visits=int(count))

    @app.get("/api/items")
    def list_items():
        try:
            docs = get_mongo()[DB_NAME][COLLECTION].find().sort("_id", -1).limit(50)
            items = [{"id": str(d["_id"]), "name": d["name"]} for d in docs]
        except Exception:  # noqa: BLE001
            return jsonify(error="mongodb unavailable"), 503
        return jsonify(items=items)

    @app.post("/api/items")
    def create_item():
        payload = request.get_json(silent=True) or {}
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            return jsonify(error="field 'name' is required"), 400
        name = name.strip()
        if len(name) > MAX_NAME_LEN:
            return jsonify(error="name is too long (max {})".format(MAX_NAME_LEN)), 400
        try:
            result = get_mongo()[DB_NAME][COLLECTION].insert_one({"name": name})
        except Exception:  # noqa: BLE001
            return jsonify(error="mongodb unavailable"), 503
        return jsonify(id=str(result.inserted_id), name=name), 201

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
