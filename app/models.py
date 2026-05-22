from pydantic import BaseModel


class BatteryState(BaseModel):
    percent: float
    source: str
    raw: dict


class MonitorSnapshot(BaseModel):
    last_percent: float | None
    last_checked_at: str | None
    last_alerted_at: str | None
    is_full: bool
