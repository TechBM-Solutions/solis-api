from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    solis_auth_mode: str = "auto"
    solis_base_url: str = "https://www.soliscloud.com:13333"
    solis_login_path: str = "/v1/api/userLogin"
    solis_battery_path: str = "/v1/api/inverterDetail"
    solis_username: str = ""
    solis_password: str = ""
    solis_plant_id: str = ""
    solis_key_id: str = ""
    solis_key_secret: str = ""

    poll_interval_seconds: int = 300
    full_battery_percent: int = 100
    weather_latitude: str = ""
    weather_longitude: str = ""
    weather_rain_threshold_mm: float = 0.1

    report_webhook_url: str = ""
    report_webhook_token: str = ""

    api_auth_enabled: bool = False
    api_auth_token: str = ""

    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
