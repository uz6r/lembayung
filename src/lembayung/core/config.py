from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """
    Core application configuration, driven by Environment Variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix=""
    )

    # Provider API configurations (Must be provided in .env)
    target_id: str
    target_slug: str
    provider_api_key: str
    provider_base_url: str = "https://api.booking-provider.com/v2"
    provider_origin: str = "https://reservation.provider.com"
    provider_referer: str = "https://reservation.provider.com/"

    # Execution Rules
    poll_interval_seconds: int = 300
    fetch_days_ahead: int = 30

    # Pax configuration
    min_pax: int = 2
    max_pax: int = 8

    # Time range filter (HH:MM format, 24h)
    # Only alert for slots within this window. Empty = all times.
    time_range_start: str | None = None  # e.g. "18:00"
    time_range_end: str | None = None  # e.g. "21:00"

    # Day filter: "everyday", "weekdays", "weekends", or comma-separated days
    # e.g. "mon,tue,fri" or "weekends"
    day_filter: str = "everyday"

    # Optional Auto-Booking configuration
    enable_auto_booking: bool = False
    dry_run: bool = True
    manual_confirmation_required: bool = True

    # DB setup
    sqlite_db_path: str = "./lembayung_state.db"

    # Notifications
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    slack_webhook_url: str | None = None

    # Rate-limiting safety
    request_delay_min: float = 1.5  # Minimum seconds between requests
    request_delay_max: float = 3.5  # Maximum seconds between requests (jitter)
    batch_cooldown_every: int = 5  # Pause every N requests
    batch_cooldown_seconds: float = 10.0  # How long to pause

    @property
    def pax_range(self) -> range:
        if self.min_pax == self.max_pax:
            return range(self.min_pax, self.min_pax + 1)
        return range(self.min_pax, self.max_pax + 1)

    @property
    def allowed_weekdays(self) -> set:
        """Returns a set of allowed weekday integers (0=Mon, 6=Sun)."""
        DAY_MAP = {
            "mon": 0,
            "tue": 1,
            "wed": 2,
            "thu": 3,
            "fri": 4,
            "sat": 5,
            "sun": 6,
        }
        filt = self.day_filter.strip().lower()
        if filt == "everyday":
            return {0, 1, 2, 3, 4, 5, 6}
        elif filt == "weekdays":
            return {0, 1, 2, 3, 4}
        elif filt == "weekends":
            return {5, 6}
        else:
            days = set()
            for d in filt.split(","):
                d = d.strip()
                if d in DAY_MAP:
                    days.add(DAY_MAP[d])
            return days if days else {0, 1, 2, 3, 4, 5, 6}

    def is_time_in_range(self, slot_time: str) -> bool:
        """Check if a slot time (HH:MM format) falls within the configured range."""
        if not self.time_range_start or not self.time_range_end:
            return True  # No filter = accept all
        try:
            start = tuple(int(x) for x in self.time_range_start.split(":"))
            end = tuple(int(x) for x in self.time_range_end.split(":"))
            slot = tuple(int(x) for x in slot_time.split(":")[:2])
            return start <= slot <= end
        except (ValueError, IndexError):
            return True  # If parsing fails, don't filter


settings = AppConfig()  # type: ignore[call-arg]
