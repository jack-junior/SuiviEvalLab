import pytest


@pytest.fixture(autouse=True)
def backup_dir(tmp_path, monkeypatch):
    """Automatic project copies go to a temporary folder, never to the user's home."""
    folder = tmp_path / "backups"
    monkeypatch.setenv("SME_BACKUP_DIR", str(folder))
    return folder


@pytest.fixture(autouse=True)
def trust_dir(tmp_path, monkeypatch):
    """R code accepted during a test is remembered in a temporary folder."""
    folder = tmp_path / "trust"
    monkeypatch.setenv("SME_TRUST_DIR", str(folder))
    return folder
