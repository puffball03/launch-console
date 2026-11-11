import pytest

from app.config import load_settings


@pytest.fixture
def make_settings(tmp_path):
    """Settings with the database in a temp dir; pass env overrides as keyword args."""

    def _make(**env):
        return load_settings({"DB_PATH": str(tmp_path / "mission.db"), **env})

    return _make
