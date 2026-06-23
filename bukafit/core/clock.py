from datetime import date, datetime
from zoneinfo import ZoneInfo

from bukafit.config import settings


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.tz)


def now_local() -> datetime:
    return datetime.now(_tz())


def today_local() -> date:
    return now_local().date()


def weekday_local() -> int:
    return now_local().isoweekday()  # Пн=1..Вс=7


def to_local_date(dt: datetime) -> date:
    return dt.astimezone(_tz()).date()
