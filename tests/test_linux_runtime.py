"""Linux user paths and real cross-process desktop lock behavior."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

from kh_app_identity import local_appdata_dir
from kh_single_instance import DesktopSingleInstanceLock


pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux runtime")


def test_linux_data_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))
    assert local_appdata_dir("khData") == str(tmp_path / "xdg-data" / "KhQuantOS" / "khData")
    monkeypatch.delenv("XDG_DATA_HOME")
    assert local_appdata_dir("khData") == str(Path.home() / ".local" / "share" / "KhQuantOS" / "khData")


def test_explicit_local_appdata_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert local_appdata_dir("logs") == str(tmp_path / "KhQuantOS" / "logs")


def test_desktop_lock_contention_and_release(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    lock = DesktopSingleInstanceLock("test-linux-desktop")
    probe = (
        "from kh_single_instance import DesktopSingleInstanceLock; "
        "lock = DesktopSingleInstanceLock('test-linux-desktop'); "
        "print(lock.acquire(), repr(lock.error)); lock.release()"
    )

    def child_probe():
        return subprocess.check_output(
            [sys.executable, "-c", probe], text=True,
            cwd=Path(__file__).resolve().parents[1], env=os.environ.copy(), timeout=10,
        ).strip()

    try:
        assert lock.acquire()
        assert not lock.error
        assert lock.acquire()
        assert child_probe() == "False ''"
    finally:
        lock.release()
    assert child_probe() == "True ''"


def test_desktop_lock_released_when_process_exits(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    subprocess.run(
        [sys.executable, "-c", (
            "import os; from kh_single_instance import DesktopSingleInstanceLock; "
            "lock = DesktopSingleInstanceLock('test-process-exit'); "
            "assert lock.acquire() and not lock.error; os._exit(0)"
        )], cwd=Path(__file__).resolve().parents[1], check=True, timeout=10,
    )
    with DesktopSingleInstanceLock("test-process-exit") as lock:
        assert not lock.error
