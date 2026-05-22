from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.config import settings
from app.models import BatteryState


class Reporter:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=20)

    async def close(self) -> None:
        await self._client.aclose()

    async def report_full_battery(self, battery: BatteryState) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        message = {
            "event": "battery_full",
            "timestamp": timestamp,
            "battery_percent": battery.percent,
            "source": battery.source,
        }

        if settings.report_webhook_url:
            headers: dict[str, str] = {}
            if settings.report_webhook_token:
                headers["Authorization"] = f"Bearer {settings.report_webhook_token}"
            await self._client.post(settings.report_webhook_url, json=message, headers=headers)

        print(f"[REPORT] {message}")
