from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hmac
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.config import settings
from app.monitor import BatteryMonitor

monitor = BatteryMonitor()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await monitor.start()
    try:
        yield
    finally:
        await monitor.stop()


app = FastAPI(title="Solis Battery Monitor API", lifespan=lifespan)


def _authorize_request(request: Request) -> None:
    if not settings.api_auth_enabled:
        return

    expected = settings.api_auth_token.strip()
    if not expected:
        raise HTTPException(status_code=500, detail="API auth is enabled but API_AUTH_TOKEN is empty")

    auth_header = request.headers.get("authorization", "")
    bearer_token = ""
    if auth_header.lower().startswith("bearer "):
        bearer_token = auth_header[7:].strip()

    api_key = request.headers.get("x-api-key", "").strip()
    if hmac.compare_digest(bearer_token, expected) or hmac.compare_digest(api_key, expected):
        return

    raise HTTPException(status_code=401, detail="Unauthorized")


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def _resolve_weather_coords() -> tuple[float | None, float | None, str]:
    env_lat = _to_float(settings.weather_latitude)
    env_lon = _to_float(settings.weather_longitude)
    if env_lat is not None and env_lon is not None:
        return env_lat, env_lon, "env"

    discovered = await monitor.client.discover_account_details()
    stations = discovered.get("station_preview") or []
    if not stations:
        return None, None, "unavailable"

    station = stations[0]
    station_lat = _to_float(station.get("latitude"))
    station_lon = _to_float(station.get("longitude"))
    if station_lat is None or station_lon is None:
        return None, None, "unavailable"

    return station_lat, station_lon, "solis_station"


async def _get_weather_gate() -> dict[str, Any]:
    lat, lon, source = await _resolve_weather_coords()
    if lat is None or lon is None:
        return {
            "available": False,
            "source": source,
            "reason": "Weather coordinates not configured or discoverable",
        }

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "is_day,precipitation,rain,weather_code,cloud_cover",
        "timezone": "auto",
    }

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get("https://api.open-meteo.com/v1/forecast", params=params)

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Weather API failed with status {response.status_code}")

    payload = response.json()
    current = payload.get("current") or {}

    precipitation = _to_float(current.get("precipitation"))
    rain = _to_float(current.get("rain"))
    is_day = int(current.get("is_day", 0)) == 1

    rain_threshold = float(settings.weather_rain_threshold_mm)
    measured_rain = max(filter(lambda x: x is not None, [precipitation, rain]), default=0.0)
    no_rain = measured_rain <= rain_threshold

    return {
        "available": True,
        "source": source,
        "latitude": lat,
        "longitude": lon,
        "is_day": is_day,
        "precipitation_mm": precipitation,
        "rain_mm": rain,
        "weather_code": current.get("weather_code"),
        "cloud_cover_percent": current.get("cloud_cover"),
        "rain_threshold_mm": rain_threshold,
        "no_rain": no_rain,
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
        return """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Solis Live SOC</title>
    <style>
        :root {
            --bg: #f6f8fa;
            --card: #ffffff;
            --text: #1f2937;
            --muted: #6b7280;
            --accent: #0ea5e9;
            --ok: #16a34a;
            --err: #dc2626;
            --border: #e5e7eb;
        }
        body {
            margin: 0;
            background: radial-gradient(circle at top left, #e0f2fe 0%, var(--bg) 45%);
            color: var(--text);
            font-family: "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif;
        }
        .wrap {
            max-width: 760px;
            margin: 48px auto;
            padding: 0 16px;
        }
        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            box-shadow: 0 8px 30px rgba(2, 8, 23, 0.06);
            padding: 24px;
        }
        h1 {
            margin: 0 0 8px;
            font-size: 28px;
            letter-spacing: 0.2px;
        }
        .muted {
            color: var(--muted);
            margin: 0 0 20px;
        }
        .soc {
            font-size: 64px;
            line-height: 1;
            font-weight: 700;
            color: var(--accent);
            margin: 8px 0 20px;
        }
        .row {
            display: grid;
            grid-template-columns: 190px 1fr;
            gap: 8px;
            margin: 8px 0;
            font-size: 15px;
        }
        .label {
            color: var(--muted);
        }
        .status {
            margin-top: 18px;
            padding: 10px 12px;
            border-radius: 10px;
            background: #f3f4f6;
            color: var(--muted);
            font-size: 14px;
        }
        .status.ok {
            color: var(--ok);
            background: #ecfdf5;
        }
        .status.err {
            color: var(--err);
            background: #fef2f2;
        }
        .actions {
            margin-top: 16px;
            display: flex;
            gap: 10px;
        }
        button {
            border: 1px solid var(--border);
            background: #ffffff;
            color: var(--text);
            border-radius: 10px;
            padding: 10px 14px;
            cursor: pointer;
            font-size: 14px;
        }
        button:hover {
            border-color: #cbd5e1;
            background: #f8fafc;
        }
    </style>
</head>
<body>
    <div class="wrap">
        <div class="card">
            <h1>Solis Live SOC</h1>
            <p class="muted">Auto-refreshes every 30 seconds.</p>

            <div id="soc" class="soc">--%</div>

            <div class="row"><div class="label">Source field</div><div id="source">--</div></div>
            <div class="row"><div class="label">Checked at (UTC)</div><div id="checked">--</div></div>
            <div class="row"><div class="label">Auth mode</div><div id="auth">--</div></div>
            <div class="row"><div class="label">Plant ID</div><div id="plant">--</div></div>
            <div class="row"><div class="label">Automation decision</div><div id="decision">--</div></div>
            <div class="row"><div class="label">Weather gate</div><div id="weather">--</div></div>

            <div id="status" class="status">Waiting for first check...</div>

            <div class="actions">
                <button id="refresh">Refresh now</button>
            </div>
        </div>
    </div>

    <script>
        const socEl = document.getElementById("soc");
        const sourceEl = document.getElementById("source");
        const checkedEl = document.getElementById("checked");
        const authEl = document.getElementById("auth");
        const plantEl = document.getElementById("plant");
        const decisionEl = document.getElementById("decision");
        const weatherEl = document.getElementById("weather");
        const statusEl = document.getElementById("status");
        const refreshBtn = document.getElementById("refresh");

        function setStatus(msg, type) {
            statusEl.textContent = msg;
            statusEl.className = "status" + (type ? " " + type : "");
        }

        async function loadData() {
            try {
                setStatus("Checking live SOC...", "");
                const [liveRes, discoverRes] = await Promise.all([
                    fetch("/live", { cache: "no-store" }),
                    fetch("/discover", { cache: "no-store" }),
                ]);
                const decisionRes = await fetch("/consumption-decision", { cache: "no-store" });

                if (!liveRes.ok) {
                    const text = await liveRes.text();
                    throw new Error("Live check failed: " + text);
                }

                const live = await liveRes.json();
                const discover = discoverRes.ok ? await discoverRes.json() : {};
                const decision = decisionRes.ok ? await decisionRes.json() : null;

                socEl.textContent = live.battery_percent.toFixed(1) + "%";
                sourceEl.textContent = live.source || "--";
                checkedEl.textContent = live.checked_at || "--";
                authEl.textContent = discover.auth_mode || "--";
                plantEl.textContent = discover.discovered_plant_id || discover.configured_plant_id || "--";
                if (decision) {
                    decisionEl.textContent = decision.allow_extra_consumption
                        ? "ALLOW extra consumption"
                        : "HOLD extra consumption";
                    weatherEl.textContent = decision.weather_gate.available
                        ? (decision.weather_gate.is_day ? "daylight" : "night") +
                          ", " +
                          (decision.weather_gate.no_rain ? "no rain" : "rain detected")
                        : "weather unavailable";
                } else {
                    decisionEl.textContent = "--";
                    weatherEl.textContent = "decision endpoint unavailable";
                }
                setStatus("Live SOC updated successfully.", "ok");
            } catch (err) {
                setStatus(String(err), "err");
            }
        }

        refreshBtn.addEventListener("click", loadData);
        loadData();
        setInterval(loadData, 30000);
    </script>
</body>
</html>
"""


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status")
async def status(request: Request) -> dict:
    _authorize_request(request)
    return monitor.snapshot().model_dump()


@app.post("/check-now")
async def check_now(request: Request) -> dict[str, float]:
    _authorize_request(request)
    try:
        percent = await monitor.check_once()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"battery_percent": percent}


@app.get("/live")
async def live(request: Request) -> dict[str, str | float]:
    _authorize_request(request)
    try:
        state = await monitor.client.get_battery_state()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "battery_percent": state.percent,
        "source": state.source,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/discover")
async def discover(request: Request) -> dict:
    _authorize_request(request)
    try:
        return await monitor.client.discover_account_details()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/consumption-decision")
async def consumption_decision(request: Request) -> dict[str, Any]:
    _authorize_request(request)
    try:
        state = await monitor.client.get_battery_state()
        weather_gate = await _get_weather_gate()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    soc_threshold = float(settings.full_battery_percent)
    soc_full = state.percent >= soc_threshold

    if not weather_gate.get("available"):
        allow = False
        reason = "SOC is ready but weather data is unavailable" if soc_full else "SOC below threshold"
    else:
        weather_ok = bool(weather_gate.get("is_day")) and bool(weather_gate.get("no_rain"))
        allow = soc_full and weather_ok
        if not soc_full:
            reason = "SOC below threshold"
        elif not bool(weather_gate.get("is_day")):
            reason = "Nighttime"
        elif not bool(weather_gate.get("no_rain")):
            reason = "Rain detected"
        else:
            reason = "Conditions favorable for surplus consumption"

    return {
        "allow_extra_consumption": allow,
        "reason": reason,
        "soc": {
            "battery_percent": state.percent,
            "threshold_percent": soc_threshold,
            "is_full": soc_full,
            "source": state.source,
        },
        "weather_gate": weather_gate,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
