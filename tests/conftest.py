import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["SUPPLYMIND_SKIP_BOOT"] = "1"   # tests build their own temporary database


@pytest.fixture()
def A(tmp_path, monkeypatch):
    """The Flask app module wired to a temporary copy of the data, database, brain and settings."""
    import app as appmod
    data = tmp_path / "data"
    shutil.copytree(os.path.join(ROOT, "data"), data)
    monkeypatch.setattr(appmod, "DATA", str(data))
    monkeypatch.setattr(appmod, "DB", str(tmp_path / "test.db"))
    monkeypatch.setattr(appmod, "BRAIN_FILE", str(tmp_path / "brain" / "brain.json"))
    monkeypatch.setattr(appmod, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    appmod.init_db(force=True)
    appmod.agent.reset()
    appmod.load_settings()
    appmod._CACHE.clear()
    appmod.app.config["TESTING"] = True
    yield appmod
    appmod.agent.reset()


@pytest.fixture()
def client(A):
    return A.app.test_client()
