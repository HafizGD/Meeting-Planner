"""Pure time logic for the Borderless Meeting Planner.

No Streamlit imports here: every function is deterministic given `now`.
Rules are defined in SPEC.md (working hours, whole-hour overlap, cell status).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence, Union
from zoneinfo import ZoneInfo

UTC = timezone.utc

WORK_START_HOUR = 9
WORK_END_HOUR = 17  # exclusive
WINDOW = timedelta(days=7)
ONE_HOUR = timedelta(hours=1)

OUTSIDE = "outside"
WORKING = "working"
OVERLAP = "overlap"

CityLike = Union["City", str]


@dataclass(frozen=True)
class City:
    name: str
    tz: str


CATALOG: tuple[City, ...] = (
    City("London", "Europe/London"),
    City("Bali", "Asia/Makassar"),
    City("Tokyo", "Asia/Tokyo"),
    City("New York", "America/New_York"),
    City("Kolkata", "Asia/Kolkata"),
    City("Los Angeles", "America/Los_Angeles"),
    City("Chicago", "America/Chicago"),
    City("Denver", "America/Denver"),
    City("São Paulo", "America/Sao_Paulo"),
    City("Buenos Aires", "America/Argentina/Buenos_Aires"),
    City("Mexico City", "America/Mexico_City"),
    City("Toronto", "America/Toronto"),
    City("Vancouver", "America/Vancouver"),
    City("Dubai", "Asia/Dubai"),
    City("Dhaka", "Asia/Dhaka"),
    City("Karachi", "Asia/Karachi"),
    City("Istanbul", "Europe/Istanbul"),
    City("Moscow", "Europe/Moscow"),
    City("Bangkok", "Asia/Bangkok"),
    City("Singapore", "Asia/Singapore"),
    City("Hong Kong", "Asia/Hong_Kong"),
    City("Shanghai", "Asia/Shanghai"),
    City("Seoul", "Asia/Seoul"),
    City("Sydney", "Australia/Sydney"),
    City("Adelaide", "Australia/Adelaide"),
    City("Auckland", "Pacific/Auckland"),
    City("Johannesburg", "Africa/Johannesburg"),
    City("Lagos", "Africa/Lagos"),
    City("Nairobi", "Africa/Nairobi"),
    City("Reykjavik", "Atlantic/Reykjavik"),
    City("Paris", "Europe/Paris"),
    City("Berlin", "Europe/Berlin"),
    City("Madrid", "Europe/Madrid"),
    City("Rome", "Europe/Rome"),
    City("Amsterdam", "Europe/Amsterdam"),
    City("Stockholm", "Europe/Stockholm"),
)

_BY_NAME: dict[str, City] = {c.name: c for c in CATALOG}


def get_city(name: str) -> City:
    try:
        return _BY_NAME[name]
    except KeyError:
        raise ValueError(f"unknown city: {name!r}") from None


def _as_city(city: CityLike) -> City:
    if isinstance(city, City):
        return city
    if isinstance(city, str):
        return get_city(city)
    raise TypeError(f"expected City or str, got {type(city).__name__}")


def _as_cities(cities: Sequence[CityLike]) -> tuple[City, ...]:
    return tuple(_as_city(c) for c in cities)


def _utc(instant: datetime, name: str = "instant") -> datetime:
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return instant.astimezone(UTC)


def local_now(city: CityLike, instant: datetime) -> datetime:
    return _utc(instant).astimezone(ZoneInfo(_as_city(city).tz))


def is_working(city: CityLike, instant: datetime) -> bool:
    local = local_now(city, instant)
    return local.weekday() < 5 and WORK_START_HOUR <= local.hour < WORK_END_HOUR


def _working_ranges(city: City, win_start: datetime, win_end: datetime) -> list[tuple[datetime, datetime]]:
    tz = ZoneInfo(city.tz)
    day = win_start.astimezone(tz).date()
    last_day = win_end.astimezone(tz).date()
    ranges: list[tuple[datetime, datetime]] = []
    while day <= last_day:
        if day.weekday() < 5:
            open_ = datetime(day.year, day.month, day.day, WORK_START_HOUR, tzinfo=tz).astimezone(UTC)
            close = datetime(day.year, day.month, day.day, WORK_END_HOUR, tzinfo=tz).astimezone(UTC)
            start, end = max(open_, win_start), min(close, win_end)
            if start < end:
                ranges.append((start, end))
        day += timedelta(days=1)
    return ranges


def _intersect(
    a: list[tuple[datetime, datetime]], b: list[tuple[datetime, datetime]]
) -> list[tuple[datetime, datetime]]:
    out: list[tuple[datetime, datetime]] = []
    i = j = 0
    while i < len(a) and j < len(b):
        start = max(a[i][0], b[j][0])
        end = min(a[i][1], b[j][1])
        if start < end:
            out.append((start, end))
        if a[i][1] <= b[j][1]:
            i += 1
        else:
            j += 1
    return out


def overlap_ranges(cities: Sequence[CityLike], now: datetime) -> list[tuple[datetime, datetime]]:
    """Minute-precision intersection of every city's working time, clipped to W."""
    now = _utc(now, "now")
    selected = _as_cities(cities)
    if not selected:
        return []
    win_end = now + WINDOW
    ranges = _working_ranges(selected[0], now, win_end)
    for city in selected[1:]:
        ranges = _intersect(ranges, _working_ranges(city, now, win_end))
        if not ranges:
            return []
    return ranges


def _ceil_hour(dt: datetime) -> datetime:
    if dt.minute or dt.second or dt.microsecond:
        return dt.replace(minute=0, second=0, microsecond=0) + ONE_HOUR
    return dt


def _floor_hour(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


def overlapping_hours(cities: Sequence[CityLike], now: datetime) -> float:
    """Whole UTC hour slots entirely inside the overlap set (SPEC §2.3)."""
    total = 0
    for start, end in overlap_ranges(cities, now):
        first, last = _ceil_hour(start), _floor_hour(end)
        if first < last:
            total += int((last - first) / ONE_HOUR)
    return float(total)


def _secs_of_day(dt: datetime) -> int:
    return dt.hour * 3600 + dt.minute * 60 + dt.second


def green_hours(city: CityLike, cities: Sequence[CityLike], now: datetime) -> frozenset[int]:
    """Local hour-of-day cells that intersect any overlap range in W (SPEC §2.4)."""
    city = _as_city(city)
    tz = ZoneInfo(city.tz)
    hours: set[int] = set()
    for start, end in overlap_ranges(cities, now):
        local_start, local_end = start.astimezone(tz), end.astimezone(tz)
        # ranges are inside the city's 09:00-17:00 working time, so both ends
        # share one local date and never cross midnight.
        s, e = _secs_of_day(local_start), _secs_of_day(local_end)
        for hour in range(WORK_START_HOUR, WORK_END_HOUR):
            if max(s, hour * 3600) < min(e, (hour + 1) * 3600):
                hours.add(hour)
    return frozenset(hours)


def _cell_status(local: datetime, hour: int, green: frozenset[int]) -> str:
    if local.weekday() >= 5 or hour < WORK_START_HOUR or hour + 1 > WORK_END_HOUR:
        return OUTSIDE
    return OVERLAP if hour in green else WORKING


def hour_cell_status(
    city: CityLike, hour: int, now: datetime, cities: Sequence[CityLike]
) -> str:
    if not 0 <= hour <= 23:
        raise ValueError(f"hour must be 0..23, got {hour!r}")
    city = _as_city(city)
    green = green_hours(city, cities, now)
    return _cell_status(local_now(city, now), hour, green)


def grid_status(cities: Sequence[CityLike], now: datetime) -> dict[str, list[str]]:
    """24 cell statuses per city, keyed in selection order (SPEC §2.4)."""
    now = _utc(now, "now")
    selected = _as_cities(cities)
    ranges = overlap_ranges(selected, now)
    grid: dict[str, list[str]] = {}
    for city in selected:
        green = green_hours(city, selected, now)
        local = local_now(city, now)
        grid[city.name] = [_cell_status(local, hour, green) for hour in range(24)]
    return grid


def utc_offset_label(city: CityLike, instant: datetime) -> str:
    offset = local_now(city, instant).utcoffset() or timedelta(0)
    total = int(offset.total_seconds())
    sign = "+" if total >= 0 else "-"
    hours, rem = divmod(abs(total), 3600)
    minutes = rem // 60
    return f"UTC{sign}{hours}" + (f":{minutes:02d}" if minutes else "")


def clock_label(city: CityLike, instant: datetime) -> str:
    local = local_now(city, instant)
    return f"{local:%A} · {utc_offset_label(city, instant)}"
