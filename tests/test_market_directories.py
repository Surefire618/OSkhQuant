"""Existing market directories retain their spelling for reads and writes."""

from pathlib import Path

import pytest

from duckdb_storage.config import resolve_market_dir, resolve_stock_db_path


@pytest.mark.parametrize("name", ["sh", "Sh", "SH"])
def test_market_path_reuses_existing_directory_without_creating_duplicate(tmp_path, name):
    existing = tmp_path / name
    existing.mkdir()
    assert Path(resolve_market_dir(str(tmp_path), "sh", create=True)).samefile(existing)
    assert Path(resolve_stock_db_path(str(tmp_path), "600000.sh", create_market=True)).parent.samefile(existing)
    assert [path.name for path in tmp_path.iterdir()] == [name]


def test_new_market_directory_uses_uppercase(tmp_path):
    result = Path(resolve_market_dir(str(tmp_path), "sz", create=True))
    assert result.name == "SZ"
    assert result.is_dir()
