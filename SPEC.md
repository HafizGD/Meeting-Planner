# SPEC — Borderless Meeting Planner

Stack: Python 3.10 · Streamlit · pytest.
Pure time logic lives in `logic.py` (no Streamlit imports); tests in `test_logic.py`; UI (`app.py`) is a follow-up.
Verification: `.venv\Scripts\pytest.exe -q`

## 1. Features (per `ui-design.png`)

**Sidebar — "Cities"**

- "Add or remove cities" chip multi-select over a fixed catalog of **36** cities.
- Counter: `2 of 36 cities selected`.
- Default selection: **London, Bali**.

**Main area**

- Title **Borderless Meeting Planner**; subtitle *"Find a window where every city is inside 09:00–17:00 local time."*
- Metric cards:
  - `Cities` — number of selected cities.
  - `Overlapping hours (next 7 days)` — one decimal, e.g. `5.0 h`.
- **Local clocks** — one block per selected city:
  - city name,
  - live local time `HH:MM:SS`,
  - badge `Tuesday · UTC+1` = local weekday · UTC offset (DST-aware; half-hour zones render `UTC+5:30`).
- **24-hour local view**:
  - legend: `Working hours` (blue) / `Overlapping hours` (green) / `Outside working hours` (gray),
  - one row per city, header `<City> — <Weekday YYYY-MM-DD> local · green = overlap` using that city's current local date,
  - cells `00`–`23` with statuses from §2.4.

## 2. Data structure

### 2.1 City catalog — fixed, exactly 36 entries

`City(name, tz)` — frozen dataclass; `tz` is an IANA key resolved with `zoneinfo.ZoneInfo`.

| City | Zone | City | Zone |
|---|---|---|---|
| London | Europe/London | Bangkok | Asia/Bangkok |
| Bali | Asia/Makassar | Singapore | Asia/Singapore |
| Tokyo | Asia/Tokyo | Hong Kong | Asia/Hong_Kong |
| New York | America/New_York | Shanghai | Asia/Shanghai |
| Kolkata | Asia/Kolkata | Seoul | Asia/Seoul |
| Los Angeles | America/Los_Angeles | Sydney | Australia/Sydney |
| Chicago | America/Chicago | Adelaide | Australia/Adelaide |
| Denver | America/Denver | Auckland | Pacific/Auckland |
| São Paulo | America/Sao_Paulo | Johannesburg | Africa/Johannesburg |
| Buenos Aires | America/Argentina/Buenos_Aires | Lagos | Africa/Lagos |
| Mexico City | America/Mexico_City | Nairobi | Africa/Nairobi |
| Toronto | America/Toronto | Reykjavik | Atlantic/Reykjavik |
| Vancouver | America/Vancouver | Paris | Europe/Paris |
| Dubai | Asia/Dubai | Berlin | Europe/Berlin |
| Dhaka | Asia/Dhaka | Madrid | Europe/Madrid |
| Karachi | Asia/Karachi | Rome | Europe/Rome |
| Istanbul | Europe/Istanbul | Amsterdam | Europe/Amsterdam |
| Moscow | Europe/Moscow | Stockholm | Europe/Stockholm |

Names are unique; the catalog is a module-level constant (`logic.CATALOG`), never mutated.

### 2.2 Working hours

A city is **within working hours** at instant `t` iff, in that city's local time:

- the weekday is Monday–Friday, **and**
- `09:00 ≤ t < 17:00` (17:00 exactly is outside).

### 2.3 Overlap window — whole hours (no minute precision)

- Window `W = [now, now + 7 days)`.
- **Overlap set** = instants in `W` where **every** selected city is within working hours (§2.2).
- **Overlapping hours = the number of whole UTC hour slots `[HH:00, HH+1:00)` lying entirely inside the overlap set.** A slot that straddles a window boundary, or that is only partially inside any city's working hours, does **not** count.
- The result is always a whole number of hours, displayed with one decimal (`5.0 h`).
- Half-hour zones make real intersections like `[08:00, 11:30) UTC` (London ∩ Kolkata) count as 3 slots, not 3.5.
- Degenerate cases: `0` cities → `0.0`; `1` city → its own 8 working hours × 5 weekdays = `40.0`.

Worked example (matches the mock): London (UTC+1, work 08:00–16:00 UTC) ∩ Bali (UTC+8, work 01:00–09:00 UTC) = `[08:00, 09:00)` UTC = **1 slot/day × 5 weekdays = 5.0 h** for `now = 2026-10-13`. Offsets are DST-aware: once London returns to GMT (Oct 25, 2026), its 09:00–17:00 UTC only *touches* Bali's window and the pair drops to `0.0 h`.

### 2.4 Cell status (24-hour view)

For city `c`, cell hour `h` (0–23), and `now`:

- `OUTSIDE` (gray): `c`'s current local weekday at `now` is Sat/Sun, **or** `h ∉ [9..16]`.
- `OVERLAP` (green): otherwise, and the local hour `[h:00, h+1:00)` intersects the local-clock image of **any** overlap range inside `W` (hour-of-day pattern taken across the whole window — so on Tue 16:22 London, cell `09` is green because it is the overlap hour on the coming days, exactly as in the mock).
- `WORKING` (blue): otherwise.
- For half-hour zones a boundary cell may be green for only part of the hour (≥ 1 minute of overlap ⇒ green).

### 2.5 Module contract — `logic.py`

```text
City, CATALOG (36), get_city(name)
local_now(city, instant)            -> aware local datetime
is_working(city, instant)           -> bool          (§2.2)
overlap_ranges(cities, now)         -> [(utc_start, utc_end)]   (minute-precision intersection, clipped to W; internal/test aid)
overlapping_hours(cities, now)      -> float         (§2.3, whole hours; cities: names or City)
green_hours(city, cities, now)      -> frozenset[int]
hour_cell_status(city, hour, now, cities) -> OUTSIDE | WORKING | OVERLAP   (§2.4; hour must be 0..23)
grid_status(cities, now)            -> {city_name: [24 statuses]}           (ordered by selection)
utc_offset_label(city, instant)     -> "UTC+1" | "UTC+5:30" | "UTC+0"
clock_label(city, instant)          -> "Tuesday · UTC+1"
OUTSIDE, WORKING, OVERLAP           -> str constants
```

All `instant`/`now` arguments must be timezone-aware; naive datetimes raise `ValueError`.

## 3. Acceptance criteria — example test cases

All times are frozen; expected values were hand-verified against the rules above.

```python
# --- clocks & catalog ---
def test_catalog_is_36_unique_valid_cities():
    assert len(logic.CATALOG) == 36
    assert len({c.name for c in logic.CATALOG}) == 36
    for c in logic.CATALOG: ZoneInfo(c.tz)          # every tz resolves

def test_local_clocks_match_mock():
    now = datetime(2026, 10, 13, 15, 22, 21, tzinfo=timezone.utc)
    assert logic.local_now(logic.get_city("London"), now)   == ...16:22:21+01:00
    assert logic.clock_label(logic.get_city("London"), now) == "Tuesday · UTC+1"
    assert logic.clock_label(logic.get_city("Bali"), now)    == "Tuesday · UTC+8"

def test_offset_label_dst_and_half_hour():
    assert logic.utc_offset_label(London, 2026, 01, 15 noon utc) == "UTC+0"   # winter
    assert logic.utc_offset_label(London, 2026, 07, 15 noon utc) == "UTC+1"   # summer
    assert logic.utc_offset_label(Kolkata, ...)                 == "UTC+5:30"

def test_is_working_boundaries():        # London, weekdays
    Tue 08:00:00Z (09:00 local) -> True
    Tue 07:59:59Z (08:59 local) -> False
    Tue 15:59:59Z (16:59 local) -> True
    Tue 16:00:00Z (17:00 local) -> False
    Sat 10:00:00Z               -> False

# --- overlap (§2.3) ---
def test_london_bali_matches_mock():      now=2026-10-13T15:22:21Z -> 5.0
def test_london_tokyo_zero():             now=2026-10-13T00:00:00Z -> 0.0   # ranges touch at 08:00 UTC, no shared slot
def test_london_new_york():               now=2026-10-13T00:00:00Z -> 15.0  # 3 slots/day (13:00–16:00 UTC) × 5
def test_london_kolkata_partial_hours():  now=2026-10-13T00:00:00Z -> 15.0  # range [08:00,11:30) UTC = 3 slots × 5; 11:00–12:00 dropped
def test_weekends_excluded():             now=2026-10-17T00:00:00Z (Sat) -> 5.0, not the naive 7.0
def test_dst_transition_in_window():      London+NY, now=2026-10-23T00:00:00Z -> 19.0
        # Fri 23: 3 slots (London BST); London GMT from Mon 26: 4 slots/day × 4 days = 16
def test_slot_straddling_window_edge_not_counted():
    London+Bali, now=2026-10-20T08:30:00Z -> 3.0   # Oct 20 / Oct 27 slots straddle the edges;
                                                     # Oct 26 contributes 0 (London already on GMT)
def test_london_bali_zero_after_gmt_transition():
    London+Bali, now=2026-10-26T00:00:00Z -> 0.0    # GMT London only touches Bali's window
def test_single_city_is_own_working_hours():  now=2026-10-13T00:00:00Z, [London] -> 40.0
def test_no_cities_is_zero():                 [] -> 0.0, overlap_ranges == []
def test_naive_now_raises():                  ValueError

# --- grid (§2.4) ---
def test_grid_matches_mock():   # now=2026-10-13T15:22:21Z, [London, Bali]
    London: 00–08 outside, 09 overlap, 10–16 working, 17–23 outside
    Bali:   00–08 outside, 09–15 working, 16 overlap,   17–23 outside

def test_grid_weekend_all_outside():        # now on Saturday -> all 24 cells outside
def test_partial_hour_cell_is_green():      # London+Kolkata, now=2026-10-13T00:00:00Z
    London cell 12 overlap (12:00–12:30), cell 13 working; Kolkata cells 13–16 overlap, cell 17 outside
def test_hour_out_of_range_raises():        # hour=-1, hour=24 -> ValueError
def test_grid_status_shape():               # keys == selection order, 24 cells each

# --- app warnings (test_app.py, AppTest) ---
def test_warning_when_no_overlap():         # Tokyo + London -> st.warning shown
def test_no_warning_when_overlap_exists():  # default London + Bali -> no warning
def test_no_warning_when_no_cities():       # [] -> info message only, no warning
```

## 4. Verification

```powershell
.venv\Scripts\Activate.ps1
.venv\Scripts\pytest.exe -q
```
