# Usage Guide

This document covers day-to-day usage, automation integration, and API contracts.

## Start The Service

```bash
make setup
make run
```

Quick checks in another terminal:

```bash
make live
make decision
```

## API At A Glance

- GET /: dashboard UI
- GET /health: service health
- GET /status: current monitor snapshot
- POST /check-now: on-demand SOC check
- GET /live: live SOC and source field
- GET /discover: Solis account discovery payload
- GET /consumption-decision: automation signal for extra consumption

## Automation Modes

### Mode A: Without credentials (trusted network)

Set in .env:

- API_AUTH_ENABLED=false

Call endpoints directly:

```bash
curl -sS http://127.0.0.1:8001/consumption-decision
```

### Mode B: With credentials (recommended when exposed)

Set in .env:

- API_AUTH_ENABLED=true
- API_AUTH_TOKEN=<long-random-token>

Use either header:

- Authorization: Bearer <API_AUTH_TOKEN>
- X-API-Key: <API_AUTH_TOKEN>

Protected endpoints:

- GET /status
- POST /check-now
- GET /live
- GET /discover
- GET /consumption-decision

Public endpoints:

- GET /
- GET /health

Examples:

```bash
curl -sS -H "Authorization: Bearer $API_AUTH_TOKEN" http://127.0.0.1:8001/consumption-decision
curl -sS -H "X-API-Key: $API_AUTH_TOKEN" http://127.0.0.1:8001/live
```

## Automation Decision Contract

Enable extra consumption only when:

- allow_extra_consumption=true

Example response from GET /consumption-decision:

```json
{
  "allow_extra_consumption": false,
  "reason": "SOC below threshold",
  "soc": {
    "battery_percent": 84.0,
    "threshold_percent": 100.0,
    "is_full": false,
    "source": "data.batteryPercent"
  },
  "weather_gate": {
    "available": true,
    "source": "solis_station",
    "latitude": 44.4568421,
    "longitude": 25.9925573,
    "is_day": false,
    "precipitation_mm": 0.0,
    "rain_mm": 0.0,
    "weather_code": 3,
    "cloud_cover_percent": 95,
    "rain_threshold_mm": 0.1,
    "no_rain": true
  },
  "checked_at": "2026-05-22T18:39:53.366458+00:00"
}
```

## Configuration Essentials

Required:

- SOLIS_USERNAME
- SOLIS_PASSWORD

Usually needed:

- SOLIS_PLANT_ID
- SOLIS_AUTH_MODE=auto|web|openapi

Weather decision tuning:

- FULL_BATTERY_PERCENT (default 100)
- WEATHER_LATITUDE (optional)
- WEATHER_LONGITUDE (optional)
- WEATHER_RAIN_THRESHOLD_MM (default 0.1)

If coordinates are not configured, the service attempts to discover them from Solis station data.

## How To Find Latitude And Longitude For Weather

Use one of these methods.

### Method 1: Automatic From Solis (recommended first)

The app can auto-discover coordinates from your Solis station.

1. Call:

```bash
curl -sS http://127.0.0.1:8001/discover
```

2. In the response, check station preview fields:

- `station_preview[0].latitude`
- `station_preview[0].longitude`

3. You can keep `WEATHER_LATITUDE` and `WEATHER_LONGITUDE` empty if those values are present.

4. Confirm weather source by calling:

```bash
curl -sS http://127.0.0.1:8001/consumption-decision
```

If `weather_gate.source` is `solis_station`, location was resolved automatically from Solis.

### Method 2: Set Coordinates Explicitly In .env

If Solis discovery is unavailable or you want a fixed location:

1. Set in `.env`:

- `WEATHER_LATITUDE=<your-latitude>`
- `WEATHER_LONGITUDE=<your-longitude>`

2. Restart the service.

3. Call `/consumption-decision` and verify `weather_gate.source` is `env`.

### Method 3: Get Coordinates From Open-Meteo Geocoding

Search by city/place name:

```bash
curl -sS "https://geocoding-api.open-meteo.com/v1/search?name=Bucharest&count=1&language=en&format=json"
```

Use `results[0].latitude` and `results[0].longitude` in `.env`.

### Quick Validation Checklist

After choosing a method, check:

1. `/consumption-decision` returns `weather_gate.available=true`
2. `weather_gate.latitude` and `weather_gate.longitude` are populated
3. `weather_gate.source` is the expected value (`env` or `solis_station`)

## Troubleshooting

- TypeError: Failed to fetch in dashboard:
  - Ensure backend is running on the same port as the browser URL.
- 502 from /live:
  - Verify Solis credentials and plant ID in .env.
- Weather unavailable in /consumption-decision:
  - Set WEATHER_LATITUDE and WEATHER_LONGITUDE explicitly.
