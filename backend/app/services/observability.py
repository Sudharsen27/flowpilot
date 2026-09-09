from datetime import datetime


def duration_ms(started_at: datetime | None, completed_at: datetime | None) -> int | None:
    if started_at is None or completed_at is None:
        return None
    elapsed = (completed_at - started_at).total_seconds()
    if elapsed < 0:
        return None
    return int(elapsed * 1000)
