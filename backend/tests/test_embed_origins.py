from app.core.embed_origins import (
    normalize_origin,
    origin_is_allowed,
    parse_allowed_origins,
    serialize_allowed_origins,
)


def test_normalize_and_serialize_origins() -> None:
    assert normalize_origin("https://www.Example.com") == "https://www.example.com"
    assert normalize_origin("http://evil.example") is None
    assert normalize_origin("https://www.example.com/path") is None
    stored = serialize_allowed_origins(
        ["https://www.example.com", "https://www.example.com", "bad"]
    )
    assert parse_allowed_origins(stored) == ["https://www.example.com"]
    assert origin_is_allowed(stored, "https://www.example.com")
    assert not origin_is_allowed(stored, "https://other.example")
