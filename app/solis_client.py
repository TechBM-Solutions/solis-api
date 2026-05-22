from __future__ import annotations

import base64
from collections.abc import Iterable
from datetime import datetime, timezone
from email.utils import formatdate
import hashlib
import hmac
import json
from typing import Any

import httpx

from app.config import settings
from app.models import BatteryState


class SolisClientError(Exception):
    pass


class SolisClient:
    _WEB_HMAC_SECRET = "5704383536604a8bb94c83ebc059aa8c"

    def __init__(self) -> None:
        self._openapi_client = httpx.AsyncClient(base_url=settings.solis_base_url, timeout=20)
        self._web_client = httpx.AsyncClient(base_url="https://www.soliscloud.com", timeout=20)
        self._token_openapi: str | None = None
        self._token_web: str | None = None

    async def close(self) -> None:
        await self._openapi_client.aclose()
        await self._web_client.aclose()

    def _use_openapi(self) -> bool:
        mode = settings.solis_auth_mode.strip().lower()
        if mode == "openapi":
            return True
        if mode == "web":
            return False
        return bool(settings.solis_key_id and settings.solis_key_secret)

    async def _authenticate(self) -> str:
        if self._use_openapi():
            return await self._authenticate_openapi()
        return await self._authenticate_web()

    async def _authenticate_openapi(self) -> str:
        if self._token_openapi:
            return self._token_openapi

        if not settings.solis_username or not settings.solis_password:
            raise SolisClientError("Missing SOLIS_USERNAME or SOLIS_PASSWORD")
        if not settings.solis_key_id or not settings.solis_key_secret:
            raise SolisClientError("Missing SOLIS_KEY_ID or SOLIS_KEY_SECRET")

        payload = {
            "userInfo": settings.solis_username,
            "passWord": settings.solis_password,
        }
        response = await self._openapi_signed_post(settings.solis_login_path, payload)
        if response.status_code >= 400:
            raise SolisClientError(
                f"Login failed with status {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        token = (
            data.get("csrfToken")
            or data.get("token")
            or data.get("data", {}).get("token")
            or data.get("data", {}).get("csrfToken")
        )
        if not token:
            raise SolisClientError("Unable to find auth token in Solis login response")

        self._token_openapi = token
        return token

    async def _authenticate_web(self) -> str:
        if self._token_web:
            return self._token_web

        if not settings.solis_username or not settings.solis_password:
            raise SolisClientError("Missing SOLIS_USERNAME or SOLIS_PASSWORD")

        payload = {
            "userInfo": settings.solis_username.strip(),
            "passWord": hashlib.md5(settings.solis_password.strip().encode("utf-8")).hexdigest(),
            "yingZhenType": 1,
        }
        response = await self._web_signed_post("/user/login2", payload)
        if response.status_code >= 400:
            raise SolisClientError(
                f"Web login failed with status {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        if str(data.get("code")) != "0":
            raise SolisClientError(f"Web login failed: {data.get('msg', 'unknown error')}")

        token = data.get("csrfToken") or data.get("data", {}).get("token")
        if not token:
            raise SolisClientError("Unable to find token in Solis web login response")

        self._token_web = token
        return token

    async def get_battery_state(self) -> BatteryState:
        if self._use_openapi():
            return await self._get_battery_state_openapi()
        return await self._get_battery_state_web()

    async def _get_battery_state_openapi(self) -> BatteryState:
        token = await self._authenticate()
        plant_id = settings.solis_plant_id or await self._discover_plant_id_openapi(token)
        payload = {"plantId": plant_id} if plant_id else {}

        response = await self._openapi_signed_post(settings.solis_battery_path, payload, token=token)
        if response.status_code == 401:
            self._token_openapi = None
            token = await self._authenticate()
            response = await self._openapi_signed_post(settings.solis_battery_path, payload, token=token)

        if response.status_code >= 400:
            raise SolisClientError(
                f"Battery request failed with status {response.status_code}: {response.text[:300]}"
            )

        raw = response.json()
        percent, source = _extract_battery_percent(raw)
        if percent is None:
            raise SolisClientError(
                "Could not extract battery percentage. Update SOLIS_BATTERY_PATH or parser fields."
            )

        return BatteryState(percent=percent, source=source, raw=raw)

    async def _get_battery_state_web(self) -> BatteryState:
        token = await self._authenticate()
        plant_id = settings.solis_plant_id
        if not plant_id:
            station_list = await self._web_signed_post(
                "/station/list", {"pageNo": 1, "pageSize": 20}, token=token
            )
            if station_list.status_code >= 400:
                raise SolisClientError(
                    f"Web station list failed with status {station_list.status_code}: {station_list.text[:300]}"
                )
            station_raw = station_list.json()
            records = (((station_raw.get("data") or {}).get("page") or {}).get("records") or [])
            if not records:
                raise SolisClientError("No stations found in Solis account")
            plant_id = str(records[0].get("id", "")).strip()

        payload = {"id": plant_id}
        response = await self._web_signed_post("/station/detailMix", payload, token=token)

        if response.status_code == 401:
            self._token_web = None
            token = await self._authenticate()
            response = await self._web_signed_post("/station/detailMix", payload, token=token)

        if response.status_code >= 400:
            raise SolisClientError(
                f"Web detailMix request failed with status {response.status_code}: {response.text[:300]}"
            )

        raw = response.json()
        if str(raw.get("code")) != "0":
            raise SolisClientError(f"Web detailMix failed: {raw.get('msg', 'unknown error')}")

        detail = raw.get("data") or {}

        direct_percent = _to_percent(detail.get("batteryPercent"))
        if direct_percent is not None:
            return BatteryState(percent=direct_percent, source="data.batteryPercent", raw=detail)

        percent, source = _extract_soc_percent(detail)
        if percent is None:
            raise SolisClientError(
                "Could not extract SOC percent from web detailMix data."
            )

        return BatteryState(percent=percent, source=source, raw=detail)

    async def discover_account_details(self) -> dict[str, Any]:
        if self._use_openapi():
            return await self._discover_account_details_openapi()
        return await self._discover_account_details_web()

    async def _discover_account_details_openapi(self) -> dict[str, Any]:
        token = await self._authenticate()
        discovered_plant_id = settings.solis_plant_id or await self._discover_plant_id_openapi(token)

        plant_endpoints = [
            "/v1/api/userStationList",
            "/v1/api/plantList",
            "/v1/api/stationList",
            "/v2/api/userStationList",
        ]
        battery_endpoints = [
            settings.solis_battery_path,
            "/v1/api/inverterDetail",
            "/v1/api/inverterList",
            "/v2/api/inverterDetail",
        ]

        plant_checks: list[dict[str, Any]] = []
        for path in plant_endpoints:
            response = await self._openapi_signed_post(path, {}, token=token)
            status_ok = response.status_code < 400
            preview = response.text[:250]
            ids = _collect_plant_ids(response.json()) if status_ok else []
            plant_checks.append(
                {
                    "path": path,
                    "status_code": response.status_code,
                    "found_plant_ids": ids[:5],
                    "response_preview": preview,
                }
            )

        battery_checks: list[dict[str, Any]] = []
        for path in battery_endpoints:
            payload = {"plantId": discovered_plant_id} if discovered_plant_id else {}
            response = await self._openapi_signed_post(path, payload, token=token)
            status_ok = response.status_code < 400
            battery_percent, source = (None, "")
            if status_ok:
                battery_percent, source = _extract_battery_percent(response.json())
            battery_checks.append(
                {
                    "path": path,
                    "status_code": response.status_code,
                    "battery_percent_detected": battery_percent,
                    "battery_source": source,
                    "response_preview": response.text[:250],
                }
            )

        return {
            "auth_mode": "openapi",
            "configured_plant_id": settings.solis_plant_id or None,
            "discovered_plant_id": discovered_plant_id,
            "configured_battery_path": settings.solis_battery_path,
            "plant_endpoint_checks": plant_checks,
            "battery_endpoint_checks": battery_checks,
        }

    async def _discover_account_details_web(self) -> dict[str, Any]:
        token = await self._authenticate()
        station_response = await self._web_signed_post("/station/list", {"pageNo": 1, "pageSize": 20}, token=token)
        inverter_response = await self._web_signed_post("/inverter/list", {"pageNo": 1, "pageSize": 50}, token=token)

        station_data = station_response.json() if station_response.status_code < 400 else {}
        inverter_data = inverter_response.json() if inverter_response.status_code < 400 else {}

        records = (((station_data.get("data") or {}).get("page") or {}).get("records") or [])
        discovered_plant_id = None
        if records:
            discovered_plant_id = str(records[0].get("id", "")) or None

        detail_mix_response = None
        detail_mix_data: dict[str, Any] = {}
        if discovered_plant_id:
            detail_mix_response = await self._web_signed_post(
                "/station/detailMix", {"id": discovered_plant_id}, token=token
            )
            if detail_mix_response.status_code < 400:
                detail_mix_data = detail_mix_response.json()

        return {
            "auth_mode": "web",
            "configured_plant_id": settings.solis_plant_id or None,
            "discovered_plant_id": discovered_plant_id,
            "station_list_status_code": station_response.status_code,
            "station_list_code": station_data.get("code"),
            "station_count": len(records),
            "station_preview": records[:2],
            "inverter_list_status_code": inverter_response.status_code,
            "inverter_list_code": inverter_data.get("code"),
            "inverter_preview": inverter_data.get("data"),
            "detail_mix_status_code": detail_mix_response.status_code if detail_mix_response else None,
            "detail_mix_code": detail_mix_data.get("code") if detail_mix_data else None,
            "detail_mix_battery_percent": (detail_mix_data.get("data") or {}).get("batteryPercent")
            if detail_mix_data
            else None,
        }

    async def _discover_plant_id_openapi(self, token: str) -> str:
        for path in ("/v1/api/userStationList", "/v1/api/plantList", "/v1/api/stationList"):
            response = await self._openapi_signed_post(path, {}, token=token)
            if response.status_code >= 400:
                continue
            ids = _collect_plant_ids(response.json())
            if ids:
                return ids[0]
        return ""

    async def _openapi_signed_post(
        self, path: str, payload: dict, token: str | None = None
    ) -> httpx.Response:
        raw_body = json.dumps(payload, separators=(",", ":"))
        headers = self._build_openapi_signed_headers(path, raw_body)
        if token:
            headers["token"] = token
        return await self._openapi_client.post(path, content=raw_body, headers=headers)

    async def _web_signed_post(
        self, path: str, payload: dict, token: str | None = None
    ) -> httpx.Response:
        body_payload = dict(payload)
        body_payload["localTime"] = int(datetime.now(timezone.utc).timestamp() * 1000)
        body_payload["localTimeZone"] = 0
        body_payload["language"] = "2"

        raw_body = json.dumps(body_payload, separators=(",", ":"))
        headers = self._build_web_signed_headers(path, raw_body)
        if token:
            headers["token"] = token
        return await self._web_client.post(f"/api{path}", content=raw_body, headers=headers)

    def _build_openapi_signed_headers(self, path: str, raw_body: str) -> dict[str, str]:
        content_type = "application/json"
        date = formatdate(usegmt=True)
        content_md5 = base64.b64encode(hashlib.md5(raw_body.encode("utf-8")).digest()).decode("utf-8")

        string_to_sign = f"POST\n{content_md5}\n{content_type}\n{date}\n{path}"
        digest = hmac.new(
            settings.solis_key_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        signature = base64.b64encode(digest).decode("utf-8")
        authorization = f"API {settings.solis_key_id}:{signature}"

        return {
            "Content-Type": content_type,
            "Content-MD5": content_md5,
            "Date": date,
            "Authorization": authorization,
        }

    def _build_web_signed_headers(self, sign_path: str, raw_body: str) -> dict[str, str]:
        content_type = "application/json"
        date = formatdate(usegmt=True)
        content_md5 = base64.b64encode(hashlib.md5(raw_body.encode("utf-8")).digest()).decode("utf-8")

        string_to_sign = f"POST\n{content_md5}\n{content_type}\n{date}\n{sign_path}"
        digest = hmac.new(
            self._WEB_HMAC_SECRET.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        signature = base64.b64encode(digest).decode("utf-8")

        return {
            "Content-Type": f"{content_type};charset=UTF-8",
            "Content-MD5": content_md5,
            "Time": date,
            "Authorization": f"WEB 2424:{signature}",
            "language": "2",
            "Device-Id": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "Version": "5.2.411",
            "platform": "Web",
            "X-Cloud-Platform": "GLY",
        }


def _extract_battery_percent(data: dict) -> tuple[float | None, str]:
    candidate_keys = {
        "batterycapacitysoc",
        "battery_soc",
        "batterysoc",
        "soc",
        "batterypercent",
        "batterypercentage",
        "battery",
    }

    def walk(node: object, path: str) -> Iterable[tuple[float, str]]:
        if isinstance(node, dict):
            for key, value in node.items():
                lower = key.lower().replace(" ", "")
                current_path = f"{path}.{key}" if path else key
                if lower in candidate_keys:
                    number = _to_percent(value)
                    if number is not None:
                        yield number, current_path
                yield from walk(value, current_path)
        elif isinstance(node, list):
            for idx, value in enumerate(node):
                yield from walk(value, f"{path}[{idx}]")

    for percent, source in walk(data, ""):
        return percent, source
    return None, ""


def _extract_soc_percent(data: dict) -> tuple[float | None, str]:
    candidate_keys = {
        "batterycapacitysoc",
        "battery_soc",
        "batterysoc",
        "soc",
        "batterypercent",
        "batterypercentage",
    }

    def walk(node: object, path: str) -> Iterable[tuple[float, str]]:
        if isinstance(node, dict):
            for key, value in node.items():
                lower = key.lower().replace(" ", "")
                current_path = f"{path}.{key}" if path else key
                if lower in candidate_keys:
                    number = _to_percent(value)
                    if number is not None:
                        yield number, current_path
                yield from walk(value, current_path)
        elif isinstance(node, list):
            for idx, value in enumerate(node):
                yield from walk(value, f"{path}[{idx}]")

    for percent, source in walk(data, ""):
        return percent, source
    return None, ""


def _collect_plant_ids(data: object) -> list[str]:
    ids: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                key_norm = key.lower().replace("_", "")
                if key_norm in {"plantid", "stationid", "id"}:
                    value_text = _to_id_text(value)
                    if value_text:
                        ids.append(value_text)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    seen: set[str] = set()
    unique_ids: list[str] = []
    for pid in ids:
        if pid not in seen:
            seen.add(pid)
            unique_ids.append(pid)
    return unique_ids


def _to_id_text(value: object) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped and stripped.lower() != "null":
            return stripped
    return ""


def _to_percent(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None
