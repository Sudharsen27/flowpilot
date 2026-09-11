import re

_HEADER_UNSAFE = re.compile(r"[\r\n]+")


def safe_header(value: str) -> str:
    return _HEADER_UNSAFE.sub("", value).strip()


def safe_optional_name(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _HEADER_UNSAFE.sub(" ", value).replace("<", "").replace(">", "").strip()
    return cleaned or None
