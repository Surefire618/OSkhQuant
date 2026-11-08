"""ETA excludes planning/login time and uses the actual download clock."""
from queue import Queue
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from duckdb_storage import baostock_import_worker as worker
from duckdb_storage import viewer
from duckdb_storage import tushare_import_worker as ts_worker


class _Label:
    def __init__(self):
        self.text = "预计剩余：--"

    def setText(self, text):
        self.text = text


class _ProgressBar:
    def setValue(self, value):
        self.value = value

    def setMaximum(self, maximum):
        self.maximum = maximum


@pytest.mark.parametrize("indicator", [False, True])
def test_baostock_eta_starts_at_download_and_keeps_first_start(monkeypatch, indicator):
    dialog = viewer.BaoStockImportDialog
    owner = SimpleNamespace(
        _import_start_time=None, _indicator_start_time=None,
        progress_bar=_ProgressBar(), indicator_progress_bar=_ProgressBar(),
        import_status_label=_Label(), indicator_status_label=_Label(),
        import_eta_label=_Label(), indicator_eta_label=_Label(),
    )
    owner._estimate_eta_text = lambda *args: dialog._estimate_eta_text(owner, *args)
    progress = dialog.on_indicator_progress if indicator else dialog.on_progress
    start = dialog.on_indicator_download_started if indicator else dialog.on_download_started
    label = owner.indicator_eta_label if indicator else owner.import_eta_label

    # Ten minutes of preparation must not become part of the per-task average.
    monkeypatch.setattr(viewer.time, "monotonic", lambda: 600.0)
    progress(owner, 0, 0, 10)
    assert label.text == "预计剩余：--"
    start(owner, 600.0)
    start(owner, 605.0)  # Later tasks/retries do not restart the batch clock.
    monkeypatch.setattr(viewer.time, "monotonic", lambda: 610.0)
    progress(owner, 10, 1, 10)
    assert label.text == "预计剩余：00:01:30"
    progress(owner, 100, 10, 10)
    assert label.text == "预计剩余：00:00:00"


def test_eta_uses_monotonic_clock_and_accepts_zero_start(monkeypatch):
    monkeypatch.setattr(viewer.time, "monotonic", lambda: 10.0)
    monkeypatch.setattr(viewer, "datetime", None)  # Wall-clock adjustments cannot affect ETA.
    estimate = viewer.BaoStockImportDialog._estimate_eta_text
    assert estimate(None, 0.0, 1, 10) == "预计剩余：00:01:30"
    assert estimate(None, None, 1, 10) == "预计剩余：--"
    assert estimate(None, 0.0, 0, 10) == "预计剩余：--"


def test_tushare_excludes_preflight_requests_and_already_current_tasks(monkeypatch):
    owner = SimpleNamespace(
        _import_start_time=None, _import_completed_at_start=0, _import_requests_at_start=0,
        progress_bar=_ProgressBar(), import_eta_label=_Label(),
    )
    dialog = viewer.TushareImportDialog
    dialog._on_download_started(owner, 600.0, 8, 20)
    dialog._on_download_started(owner, 605.0, 9, 22)
    monkeypatch.setattr(viewer.time, "monotonic", lambda: 610.0)
    # Eight current tasks were skipped before downloading; one real task took 10 s.
    dialog._on_progress(owner, 9, 10, 22, 22)
    assert owner.import_eta_label.text == (
        "进度：9/10 | 请求数：22 (12.0次/分) | 预计剩余：0分10秒"
    )


@pytest.mark.parametrize("task_kind", ["kline", "indicator", "adjustment"])
@pytest.mark.parametrize("fail", [False, True])
def test_baostock_worker_timestamps_after_login_before_fetch(monkeypatch, task_kind, fail):
    import baostock_proxy

    clock = {"now": 0.0}
    monkeypatch.setattr(worker.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(baostock_proxy, "enable_baostock_proxy", lambda: None)
    monkeypatch.setitem(sys.modules, "baostock", SimpleNamespace(logout=lambda: None))

    def login(*_args):
        clock["now"] = 600.0
        return SimpleNamespace(error_code="0")

    def fetch(*_args):
        clock["now"] = 610.0
        if fail:
            raise RuntimeError("download failed")
        return pd.DataFrame()

    monkeypatch.setattr(worker, "_login_with_backoff", login)
    monkeypatch.setattr(worker, "_fetch_kline_once", fetch)
    monkeypatch.setattr(worker, "_fetch_indicators_once", fetch)
    tasks, results, progress = Queue(), Queue(), Queue()
    tasks.put(dict(task_id=1, stock_code="000001.SZ", bs_code="sz.000001",
                   period="1d", start_date="2024-01-02", end_date="2024-01-03",
                   task_kind=task_kind))
    tasks.put(None)
    worker._baostock_download_worker(tasks, results, progress)
    result = results.get_nowait()
    events = []
    while not progress.empty():
        events.append(progress.get_nowait())
    started = next(event for event in events if event["type"] == "started")
    assert started["started_at"] == result["started_at"] == 600.0
    assert result["success"] is not fail


@pytest.mark.parametrize("needs_download", [False, True])
def test_tushare_thread_signals_only_after_preparation_and_skips(monkeypatch, needs_download):
    clock = {"now": 0.0}
    monkeypatch.setattr(ts_worker.time, "monotonic", lambda: clock["now"])
    importer = SimpleNamespace(request_count=0, request_times=[])

    def prepare():
        clock["now"] = 200.0
        importer.request_count = 5
        return True, "ok"

    importer.test_connection = prepare
    importer.get_latest_trade_date = lambda: "20240103"
    monkeypatch.setattr(ts_worker, "TushareImporter", lambda **_kwargs: importer)
    thread = ts_worker.TushareImportThread(
        token="test", use_proxy=False, proxy_url="", manager=SimpleNamespace(),
        stock_list=["000001.SZ", "000002.SZ"],
        periods=[dict(period="1d", start_date="20240102", end_date="20240103")],
    )
    monkeypatch.setattr(thread, "_ensure_benchmark_data", lambda *_args: 0)
    monkeypatch.setattr(thread, "_plan_download_specs", lambda plan, _period: plan.download_ranges)

    def scan(_manager, stock, *_args, **_kwargs):
        clock["now"] += 200.0
        missing = needs_download and stock == "000002.SZ"
        return SimpleNamespace(
            expected_dates=("20240102",), partial_dates=(),
            download_ranges=[("20240102", "20240103", False)] if missing else [],
        )

    monkeypatch.setattr(thread, "_get_incremental_plan", scan)
    starts = []
    thread.download_started.connect(lambda *args: starts.append(args))

    def download(*_args):
        assert starts == [(600.0, 1, 5)]
        thread.stop()
        raise ts_worker._AbortImport("test completed")

    monkeypatch.setattr(thread, "_download_raw_frame", download)
    thread.run()
    assert starts == ([(600.0, 1, 5)] if needs_download else [])
    assert thread.last_results["up_to_date"] == (1 if needs_download else 2)
