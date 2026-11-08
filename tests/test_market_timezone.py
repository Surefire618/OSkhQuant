"""Market timestamps and trigger clocks must not depend on the host timezone."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import time

import numpy as np
import pandas as pd
import pytest

import khFrame
from khDynamicLoader import DynamicDataLoader
from duckdb_storage.time_utils import market_datetime_fromtimestamp, market_timestamp


SHANGHAI = timezone(timedelta(hours=8))


@pytest.fixture(params=["Asia/Shanghai", "Europe/Berlin", "America/New_York", "UTC"])
def host_timezone(request, monkeypatch):
    if not hasattr(time, "tzset"):
        pytest.skip("Changing the process timezone requires POSIX tzset")
    with monkeypatch.context() as context:
        context.setenv("TZ", request.param)
        time.tzset()
        try:
            yield request.param
        finally:
            context.undo()
            time.tzset()


@pytest.mark.parametrize("day", ["2024-01-02", "2024-07-02"])
def test_market_day_and_loader_date_are_independent_of_host_timezone(host_timezone, day):
    wall_time = datetime.fromisoformat(day)
    expected = int(wall_time.replace(tzinfo=SHANGHAI).timestamp())
    assert market_timestamp(wall_time) == expected
    assert market_timestamp(datetime.fromtimestamp(expected, timezone.utc)) == expected
    assert market_datetime_fromtimestamp(expected) == wall_time
    loader = object.__new__(DynamicDataLoader)
    for value in (expected, expected * 1000):
        assert loader._time_to_date_str(value) == day.replace("-", "")
        assert khFrame._normalize_daily_time_values([value]).tolist() == [value]
    aware_utc = pd.Timestamp(expected, unit="s", tz="UTC")
    assert khFrame._normalize_daily_time_values([aware_utc]).tolist() == [expected]
    assert khFrame._index_strings_to_local_epoch_seconds([day.replace("-", "") + "000000"]).tolist() == [expected]


def test_tick_window_and_custom_axis_use_shanghai_time(host_timezone):
    ticks = pd.to_datetime([
        "2024-01-02 09:59:57.500", "2024-01-02 09:59:59.500", "2024-01-02 10:00:00.500",
    ]).values
    trigger = int(datetime(2024, 1, 2, 10, tzinfo=SHANGHAI).timestamp())
    seconds = np.array([trigger - 2.5, trigger - 0.5, trigger + 0.5])
    for values in (ticks, ticks.astype("datetime64[us]"), seconds, seconds * 1000):
        assert khFrame._custom_tick_asof_index(values, [36000]) == {trigger: 1}
        assert khFrame._custom_trigger_keep_mask(values, [36000], True).tolist() == [True, True, False]
    framework = SimpleNamespace(
        config=SimpleNamespace(backtest_start="20240102", backtest_end="20240102"),
        trigger=SimpleNamespace(trigger_seconds=[36000]),
        tools=SimpleNamespace(is_trade_day=lambda _: True),
    )
    assert khFrame.KhQuantFramework._custom_trigger_time_axis(framework) == [trigger]


@pytest.mark.parametrize("milliseconds", [False, True])
def test_callback_clock_and_record_timestamp_use_shanghai_time(host_timezone, milliseconds):
    expected = int(datetime(2024, 1, 2, 8, 30, tzinfo=SHANGHAI).timestamp())
    info = khFrame._callback_time_info({}, "2024-01-02", "08:30:00", milliseconds)
    assert info["timestamp"] == expected * (1000 if milliseconds else 1)
    assert info["_dt"] == datetime(2024, 1, 2, 8, 30)
    assert khFrame._time_info_epoch_seconds(info) == expected
    del info["_dt"]
    assert khFrame._time_info_epoch_seconds(info) == expected
