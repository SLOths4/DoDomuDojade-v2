from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ddd:ddd@localhost:5432/dodomudojade"
    secret_key: str = "change-me"
    timezone: str = "Europe/Warsaw"
    log_level: str = "INFO"
    contact_email: str = "sloths4@spolecznaczworka.pl"

    cookie_secure: bool = False
    session_max_age_days: int = 7
    scheduler_enabled: bool = True

    data_dir: str = "data"

    stop_name: str = "AWF"
    stop_codes: str = ""

    imgw_weather_url: str = ""
    airly_api_key: str = ""
    airly_location_id: str = ""

    google_service_account_file: str = ""
    google_calendar_id: str = ""

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def user_agent(self) -> str:
        return f"DoDomuDojade/2 ({self.contact_email})"


@lru_cache
def get_settings() -> Settings:
    return Settings()
