"""Шлюз (замена nginx): единственная точка входа.

/api/*  -> сервис api
всё остальное -> сервис web
"""
import os

import requests
from flask import Flask, Response, request

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

# заголовки, которые нельзя пробрасывать как есть
SKIP_REQUEST_HEADERS = {"host", "content-length", "connection", "accept-encoding"}
SKIP_RESPONSE_HEADERS = {
    "connection",
    "keep-alive",
    "transfer-encoding",
    "content-encoding",  # requests уже распаковал тело
    "content-length",
}


def create_app(session=None, api_url=None, web_url=None):
    # static_folder=None: свой маршрут /static у Flask не должен перехватывать запросы
    app = Flask(__name__, static_folder=None)
    http = session or requests.Session()
    api_base = (api_url or os.environ.get("API_URL", "http://api:3000")).rstrip("/")
    web_base = (web_url or os.environ.get("WEB_URL", "http://web:8000")).rstrip("/")

    @app.route("/", defaults={"path": ""}, methods=METHODS)
    @app.route("/<path:path>", methods=METHODS)
    def proxy(path):
        is_api = path == "api" or path.startswith("api/")
        base = api_base if is_api else web_base

        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in SKIP_REQUEST_HEADERS
        }
        headers["X-Forwarded-For"] = request.remote_addr or ""
        headers["X-Forwarded-Host"] = request.host

        try:
            upstream = http.request(
                method=request.method,
                url="{}/{}".format(base, path),
                params=request.args,
                data=request.get_data(),
                headers=headers,
                allow_redirects=False,
                timeout=10,
            )
        except requests.RequestException:
            return Response("Bad gateway\n", status=502, mimetype="text/plain")

        out_headers = [
            (k, v) for k, v in upstream.headers.items()
            if k.lower() not in SKIP_RESPONSE_HEADERS
        ]
        return Response(upstream.content, status=upstream.status_code, headers=out_headers)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
