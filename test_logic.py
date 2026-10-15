"""Acceptance tests for logic.py — SPEC.md §3 (frozen times, hand-verified values)."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

import logic

UTC = timezone.utc


def ts(*args) -> datetime:
    return datetime(*args, tzinfo=UTC)


LONDON = logic.get_city("London")
BALI = logic.get_city("Bali")
TOKYO = logic.get_city("Tokyo")
KOLKATA = logic.get_city("Kolkata")
NEW_YORK = logic.get_city("New York")

MOCK_NOW = ts(2026, 10, 13, 15, 22, 21)  # Tue, clock 16:22:21 London / 23:22:21 Bali
MIDNIGHT = ts(2026, 10, 13, 0, 0, 0)


# --- catalog & clocks -------------------------------------------------

def test_catalog_is_36_unique_valid_cities():
    assert len(logic.CATALOG) == 36
    assert len({c.name for c in logic.CATALOG}) == 36
    for c in logic.CATALOG:
        ZoneInfo(c.tz)


def test_default_selection_cities_exist():
    for name in ("London", "Bali"):
        logic.get_city(name)


def test_get_city_unknown_raises():
    with pytest.raises(ValueError):
        logic.get_city("Atlantis")


def test_local_clocks_match_mock():
    assert logic.local_now(LONDON, MOCK_NOW).strftime("%H:%M:%S") == "16:22:21"
    assert logic.local_now(BALI, MOCK_NOW).strftime("%H:%M:%S") == "23:22:21"
    assert logic.clock_label(LONDON, MOCK_NOW) == "Tuesday · UTC+1"
    assert logic.clock_label(BALI, MOCK_NOW) == "Tuesday · UTC+8"


def test_offset_label_dst_and_half_hour():
    assert logic.utc_offset_label(LONDON, ts(2026, 1, 15, 12)) == "UTC+0"
    assert logic.utc_offset_label(LONDON, ts(2026, 7, 15, 12)) == "UTC+1"
    assert logic.utc_offset_label(KOLKATA, MOCK_NOW) == "UTC+5:30"
    assert logic.utc_offset_label(NEW_YORK, MOCK_NOW) == "UTC-4"


def test_is_working_boundaries():
    assert logic.is_working(LONDON, ts(2026, 10, 13, 8, 0, 0)) is True    # 09:00 local
    assert logic.is_working(LONDON, ts(2026, 10, 13, 7, 59, 59)) is False  # 08:59 local
    assert logic.is_working(LONDON, ts(2026, 10, 13, 15, 59, 59)) is True  # 16:59 local
    assert logic.is_working(LONDON, ts(2026, 10, 13, 16, 0, 0)) is False   # 17:00 local
    assert logic.is_working(LONDON, ts(2026, 10, 17, 10, 0, 0)) is False   # Saturday


def test_naive_now_raises():
    with pytest.raises(ValueError):
        logic.overlapping_hours(["London", "Bali"], datetime(2026, 10, 13, 12))
    with pytest.raises(ValueError):
        logic.local_now(LONDON, datetime(2026, 10, 13, 12))


# --- overlap window (SPEC §2.3) ---------------------------------------

def test_london_bali_matches_mock():
    assert logic.overlapping_hours(["London", "Bali"], MOCK_NOW) == 5.0


def test_london_tokyo_zero():
    cities = ["London", "Tokyo"]
    assert logic.overlap_ranges(cities, MIDNIGHT) == []
    assert logic.overlapping_hours(cities, MIDNIGHT) == 0.0


def test_london_new_york():
    assert logic.overlapping_hours(["London", "New York"], MIDNIGHT) == 15.0


def test_london_kolkata_partial_hours_dropped():
    cities = ["London", "Kolkata"]
    ranges = logic.overlap_ranges(cities, MIDNIGHT)
    assert ranges[0] == (ts(2026, 10, 13, 8, 0), ts(2026, 10, 13, 11, 30))
    assert logic.overlapping_hours(cities, MIDNIGHT) == 15.0  # 3 slots/day × 5, not 17.5


def test_weekends_excluded():
    # Saturday start: a naive 7-day sum would count Sat 17 .. Fri 23 = 7.0
    assert logic.overlapping_hours(["London", "Bali"], ts(2026, 10, 17, 0, 0)) == 5.0


def test_dst_transition_in_window():
    cities = ["London", "New York"]
    now = ts(2026, 10, 23, 0, 0)  # Friday; London BST->GMT on Sun Oct 25
    ranges = logic.overlap_ranges(cities, now)
    assert ranges[0] == (ts(2026, 10, 23, 13, 0), ts(2026, 10, 23, 16, 0))   # London BST: 3 slots
    assert ranges[1] == (ts(2026, 10, 26, 13, 0), ts(2026, 10, 26, 17, 0))   # London GMT: 4 slots
    assert logic.overlapping_hours(cities, now) == 19.0  # 3 + 4×4


def test_slot_straddling_window_edge_not_counted():
    now = ts(2026, 10, 20, 8, 30)  # Oct 20 slot straddles start, Oct 27 slot straddles end
    assert logic.overlapping_hours(["London", "Bali"], now) == 3.0  # only Oct 21, 22, 23


def test_london_bali_zero_after_gmt_transition():
    # London BST->GMT on Sun Oct 25: London 09:00-17:00 UTC only touches Bali's 01:00-09:00 UTC
    assert logic.overlapping_hours(["London", "Bali"], ts(2026, 10, 26, 0, 0)) == 0.0


def test_single_city_is_own_working_hours():
    assert logic.overlapping_hours(["London"], MIDNIGHT) == 40.0  # 8h × 5 weekdays


def test_no_cities_is_zero():
    assert logic.overlap_ranges([], MIDNIGHT) == []
    assert logic.overlapping_hours([], MIDNIGHT) == 0.0


# --- 24-hour grid (SPEC §2.4) -----------------------------------------

def test_grid_matches_mock():
    grid = logic.grid_status(["London", "Bali"], MOCK_NOW)

    london = grid["London"]
    assert london[0:9] == [logic.OUTSIDE] * 9
    assert london[9] == logic.OVERLAP
    assert london[10:17] == [logic.WORKING] * 7
    assert london[17:24] == [logic.OUTSIDE] * 7

    bali = grid["Bali"]
    assert bali[0:9] == [logic.OUTSIDE] * 9
    assert bali[9:16] == [logic.WORKING] * 7
    assert bali[16] == logic.OVERLAP
    assert bali[17:24] == [logic.OUTSIDE] * 7


def test_grid_weekend_all_outside():
    grid = logic.grid_status(["London", "Bali"], ts(2026, 10, 17, 12, 0))  # Saturday
    assert grid["London"] == [logic.OUTSIDE] * 24
    assert grid["Bali"] == [logic.OUTSIDE] * 24


def test_partial_hour_cell_is_green():
    cities = ["London", "Kolkata"]
    assert logic.hour_cell_status(LONDON, 12, MIDNIGHT, cities) == logic.OVERLAP  # 12:00-12:30
    assert logic.hour_cell_status(LONDON, 13, MIDNIGHT, cities) == logic.WORKING
    assert logic.hour_cell_status(KOLKATA, 13, MIDNIGHT, cities) == logic.OVERLAP  # starts 13:30
    assert logic.hour_cell_status(KOLKATA, 16, MIDNIGHT, cities) == logic.OVERLAP  # ends 16:30
    assert logic.hour_cell_status(KOLKATA, 17, MIDNIGHT, cities) == logic.OUTSIDE


def test_hour_out_of_range_raises():
    for bad in (-1, 24):
        with pytest.raises(ValueError):
            logic.hour_cell_status(LONDON, bad, MOCK_NOW, ["London", "Bali"])


def test_grid_status_shape():
    grid = logic.grid_status(["Bali", "London"], MOCK_NOW)
    assert list(grid) == ["Bali", "London"]  # selection order
    assert all(len(cells) == 24 for cells in grid.values())
