from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_alembic_discovers_a_single_head() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    assert len(heads) == 1
    assert heads[0]


def test_forecast_snapshots_revise_036_while_037_is_reserved() -> None:
    """038 follows 036 directly: 037 (the 4C contract step) is held until the 4C release
    is serving in production, and will revise 038 when it ships."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(config)
    snapshots = script.get_revision("038_forecast_snapshots")
    assert snapshots is not None
    assert snapshots.down_revision == "036_deal_forecast_category"
    assert script.get_heads() == ["038_forecast_snapshots"]
    assert not any(rev.revision.startswith("037") for rev in script.walk_revisions())
