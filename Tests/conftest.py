"""Shared pytest fixtures."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def isolated_app_data(tmp_path, monkeypatch):
    """Keep the undo journal of every test in tmp_path.

    The rename engine, timestamp sync and time shift write to the undo
    journal in the user's app-data directory; without this, running the
    tests would fill the real journal with temporary paths (and the app
    would offer to "recover" them on its next start).
    """
    from modules import backup_journal

    app_data = tmp_path / "app_data"
    app_data.mkdir()
    monkeypatch.setattr(backup_journal, "get_app_data_dir", lambda: str(app_data))
    return app_data
