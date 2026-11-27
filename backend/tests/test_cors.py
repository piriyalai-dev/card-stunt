"""CORS ของ deployment จริง — frontend อยู่คนละ subdomain จาก API."""


def _preflight(client, origin: str):
    return client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )


def test_cors_allows_production_frontend(client):
    origin = "https://pixel.singto1597.xyz"
    r = _preflight(client, origin)
    assert r.status_code == 200, r.text
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_allows_dev_server(client):
    origin = "http://localhost:5173"
    r = _preflight(client, origin)
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_rejects_unknown_origin(client):
    r = _preflight(client, "https://evil.example")
    assert r.headers.get("access-control-allow-origin") is None
