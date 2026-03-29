"""Tests for scripts/data_provider.py."""

import pandas as pd
import pytest

from data_provider import DataProviderRouter


def test_router_akshare_direct_fetch(monkeypatch):
    expected = pd.DataFrame([{"x": 1}])

    def _fake_fetch(api_name, **kwargs):
        assert api_name == "daily_basic"
        assert kwargs["ts_code"] == "600887.SH"
        return expected

    monkeypatch.setattr("data_provider.ak_fetch", _fake_fetch)
    router = DataProviderRouter("akshare")
    out = router.direct_fetch("daily_basic", ts_code="600887.SH")
    assert out.equals(expected)


def test_router_tushare_no_direct_fetch():
    router = DataProviderRouter("tushare")
    with pytest.raises(RuntimeError, match="direct_fetch"):
        router.direct_fetch("daily_basic", ts_code="600887.SH")


def test_router_fallback_on_permission_error(monkeypatch):
    expected = pd.DataFrame([{"y": 2}])

    def _fake_can_fallback(err):
        return "权限" in str(err)

    def _fake_fetch(api_name, **kwargs):
        assert api_name == "daily_basic"
        return expected

    monkeypatch.setattr("data_provider.ak_can_fallback", _fake_can_fallback)
    monkeypatch.setattr("data_provider.ak_fetch", _fake_fetch)

    router = DataProviderRouter("tushare")
    out = router.fallback_fetch(RuntimeError("没有接口访问权限"), "daily_basic", ts_code="600887.SH")
    assert out is not None
    assert out.equals(expected)


def test_router_fallback_none_when_not_permission(monkeypatch):
    monkeypatch.setattr("data_provider.ak_can_fallback", lambda err: False)
    router = DataProviderRouter("tushare")
    out = router.fallback_fetch(RuntimeError("random error"), "daily_basic", ts_code="600887.SH")
    assert out is None
