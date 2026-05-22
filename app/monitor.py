from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.config import settings
from app.models import MonitorSnapshot
from app.notifier import Reporter
from app.solis_client import SolisClient, SolisClientError


class BatteryMonitor:
    def __init__(self) -> None:
        self.client = SolisClient()
        self.reporter = Reporter()

        self.last_percent: float | None = None
        self.last_checked_at: datetime | None = None
        self.last_alerted_at: datetime | None = None
        self.is_full = False

        self._task: asyncio.Task | None = None
        self._stopped = asyncio.Event()

    async def start(self) -> None:
        self._stopped.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopped.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.client.close()
        await self.reporter.close()

    async def check_once(self) -> float:
        state = await self.client.get_battery_state()

        self.last_percent = state.percent
        self.last_checked_at = datetime.now(timezone.utc)

        threshold = float(settings.full_battery_percent)
        now_full = state.percent >= threshold

        if now_full and not self.is_full:
            await self.reporter.report_full_battery(state)
            self.last_alerted_at = datetime.now(timezone.utc)

        self.is_full = now_full
        return state.percent

    async def _run(self) -> None:
        while not self._stopped.is_set():
            try:
                await self.check_once()
            except SolisClientError as exc:
                print(f"[ERROR] Solis monitor error: {exc}")
            except Exception as exc:
                print(f"[ERROR] Unexpected monitor error: {exc}")

            await asyncio.sleep(settings.poll_interval_seconds)

    def snapshot(self) -> MonitorSnapshot:
        return MonitorSnapshot(
            last_percent=self.last_percent,
            last_checked_at=self.last_checked_at.isoformat() if self.last_checked_at else None,
            last_alerted_at=self.last_alerted_at.isoformat() if self.last_alerted_at else None,
            is_full=self.is_full,
        )
