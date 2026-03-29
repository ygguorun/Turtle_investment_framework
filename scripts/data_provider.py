"""Provider routing for Tushare/AkShare data access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from akshare_provider import can_fallback as ak_can_fallback
from akshare_provider import fetch as ak_fetch
from config import get_data_provider


@dataclass(frozen=True)
class ProviderSettings:
    name: str
    fallback_on_permission_error: bool = True


class DataProviderRouter:
    """Route API calls to the active provider with optional fallback."""

    def __init__(self, provider: Optional[str] = None,
                 fallback_on_permission_error: bool = True):
        name = (provider or get_data_provider()).strip().lower()
        if name not in {"tushare", "akshare"}:
            raise RuntimeError(f"Unsupported provider: {name}")
        self.settings = ProviderSettings(
            name=name,
            fallback_on_permission_error=fallback_on_permission_error,
        )

    @property
    def name(self) -> str:
        return self.settings.name

    def use_akshare(self) -> bool:
        return self.settings.name == "akshare"

    def direct_fetch(self, api_name: str, **kwargs) -> pd.DataFrame:
        """Fetch directly from configured provider.

        Only used for provider=akshare mode; tushare direct call should still
        go through existing client logic for retry, rate-limit, and VIP mapping.
        """
        if not self.use_akshare():
            raise RuntimeError("direct_fetch is only valid in akshare mode")
        return ak_fetch(api_name, **kwargs)

    def fallback_fetch(self, err: Exception, api_name: str,
                       **kwargs) -> Optional[pd.DataFrame]:
        """Return AkShare fallback DataFrame if fallback condition matches."""
        if self.use_akshare() or not self.settings.fallback_on_permission_error:
            return None
        if not ak_can_fallback(err):
            return None
        return ak_fetch(api_name, **kwargs)
