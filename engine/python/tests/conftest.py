import pytest


@pytest.fixture(autouse=True)
def backup_dir(tmp_path, monkeypatch):
    """Automatic project copies go to a temporary folder, never to the user's home."""
    folder = tmp_path / "backups"
    monkeypatch.setenv("SME_BACKUP_DIR", str(folder))
    return folder
