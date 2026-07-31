from starlette.requests import Request

from prairie_signal_api.logging import privacy_safe_log_fields


def test_privacy_safe_fields_exclude_query_coordinates_and_client_ip() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/weather/current",
        "query_string": b"latitude=40.8136&longitude=-96.7026",
        "headers": [(b"user-agent", b"private")],
        "client": ("203.0.113.42", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
        "root_path": "",
    }
    request = Request(scope)

    fields = privacy_safe_log_fields(request)

    assert fields == {"method": "GET", "route": "<unmatched>"}
    rendered = repr(fields)
    assert "40.8136" not in rendered
    assert "203.0.113.42" not in rendered
