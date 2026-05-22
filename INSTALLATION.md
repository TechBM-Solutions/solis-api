# Installation Guide

After installation, continue with:

- [USAGE.md](USAGE.md) for endpoint and automation usage
- [PUBLIC_RELEASE.md](PUBLIC_RELEASE.md) for pre-publish checks

## Prerequisites

- Linux/macOS shell (or WSL on Windows)
- Python 3.11+
- Internet access (Solis API + Open-Meteo weather API)

## 1) Clone and enter project

```bash
git clone <your-repo-url> solis-api
cd solis-api
```

## 2) Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

## 3) Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 4) Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your real Solis credentials:

- `SOLIS_USERNAME`
- `SOLIS_PASSWORD`
- `SOLIS_PLANT_ID`

Optional for weather policy:

- `WEATHER_LATITUDE`
- `WEATHER_LONGITUDE`
- `WEATHER_RAIN_THRESHOLD_MM`

Optional for external tool authentication:

- `API_AUTH_ENABLED=true`
- `API_AUTH_TOKEN=<long-random-token>`

## 5) Run server

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Open:

- Dashboard: http://127.0.0.1:8001/
- Health: http://127.0.0.1:8001/health
- Live SOC: http://127.0.0.1:8001/live
- Decision: http://127.0.0.1:8001/consumption-decision

## 6) Fast usage with Makefile (recommended)

```bash
make setup
make run
```

In another terminal:

```bash
make live
make decision
```

With credentials enabled:

```bash
curl -sS -H "Authorization: Bearer $API_AUTH_TOKEN" http://127.0.0.1:8001/live
curl -sS -H "Authorization: Bearer $API_AUTH_TOKEN" http://127.0.0.1:8001/consumption-decision
```

## Troubleshooting

- `TypeError: Failed to fetch` in dashboard:
  - Ensure backend is running on the same port shown in browser URL.
- `502` from `/live`:
  - Check Solis credentials and plant ID in `.env`.
- `No stations found`:
  - Verify account has access to the plant and `SOLIS_PLANT_ID` is correct.
- Weather unavailable in decision endpoint:
  - Set `WEATHER_LATITUDE` and `WEATHER_LONGITUDE` explicitly in `.env`.
