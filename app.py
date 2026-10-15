"""Borderless Meeting Planner — Streamlit UI (SPEC.md §1).

All time rules come from logic.py; this file only renders.
"""

from datetime import datetime, timedelta, timezone

import streamlit as st

import logic

st.set_page_config(page_title="Borderless Meeting Planner", layout="wide")

CSS = """
<style>
.clock { font-size: 2rem; font-weight: 600; line-height: 1.2; }
.badge { display: inline-block; background: #f1f3f5; color: #495057;
         border-radius: 999px; padding: 2px 10px; font-size: 0.8rem; }
.legend-chip { display: inline-block; border-radius: 999px; padding: 3px 12px;
               font-size: 0.85rem; margin-right: 8px; }
.lg-working { background: #cfe2ff; color: #084298; }
.lg-overlap { background: #198754; color: white; }
.lg-outside { background: #f1f3f5; color: #868e96; }
.row-title { font-weight: 600; margin: 14px 0 6px; }
.row { white-space: nowrap; }
.cell { display: inline-flex; align-items: center; justify-content: center;
        width: 38px; height: 30px; margin-right: 4px; border-radius: 6px;
        font-size: 0.85rem; font-variant-numeric: tabular-nums; }
.cell-working { background: #cfe2ff; color: #084298; }
.cell-overlap { background: #198754; color: white; font-weight: 600; }
.cell-outside { background: #f1f3f5; color: #adb5bd; }
</style>
"""

LEGEND = (
    "<span class='legend-chip lg-working'>Working hours</span>"
    "<span class='legend-chip lg-overlap'>Overlapping hours</span>"
    "<span class='legend-chip lg-outside'>Outside working hours</span>"
)

st.markdown(CSS, unsafe_allow_html=True)

# --- sidebar -----------------------------------------------------------

st.sidebar.header("Cities")
selected: list[str] = st.sidebar.multiselect(
    "Add or remove cities",
    options=[c.name for c in logic.CATALOG],
    default=["London", "Bali"],
)
st.sidebar.caption(f"{len(selected)} of {len(logic.CATALOG)} cities selected")

# --- header & metrics --------------------------------------------------

st.title("Borderless Meeting Planner")
st.caption("Find a window where every city is inside 09:00–17:00 local time.")

now = datetime.now(timezone.utc)
cities = [logic.get_city(name) for name in selected]
overlap = logic.overlapping_hours(cities, now)

metric_a, metric_b = st.columns(2)
metric_a.metric("Cities", len(selected))
metric_b.metric("Overlapping hours (next 7 days)", f"{overlap:.1f} h")

if selected and overlap == 0.0:
    st.warning(
        "No overlapping hours in the next 7 days — there is no time window "
        "where every city is inside 09:00–17:00 local time."
    )


# --- local clocks (ticks every second) ---------------------------------

@st.fragment(run_every=timedelta(seconds=1))
def render_clocks(names: list[str]) -> None:
    tick = datetime.now(timezone.utc)
    for start in range(0, len(names), 4):
        cols = st.columns(min(4, len(names) - start))
        for col, name in zip(cols, names[start : start + 4]):
            city = logic.get_city(name)
            with col:
                st.markdown(f"**{name}**")
                st.markdown(
                    f"<div class='clock'>{logic.local_now(city, tick):%H:%M:%S}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<span class='badge'>{logic.clock_label(city, tick)}</span>",
                    unsafe_allow_html=True,
                )


# --- 24-hour local view -------------------------------------------------

def hour_cell_html(hour: int, status: str) -> str:
    return f"<span class='cell cell-{status}'>{hour:02d}</span>"


if selected:
    st.subheader("Local clocks")
    render_clocks(selected)

    st.subheader("24-hour local view")
    st.markdown(LEGEND, unsafe_allow_html=True)
    grid = logic.grid_status(cities, now)
    for city in cities:
        local = logic.local_now(city, now)
        cells = "".join(
            hour_cell_html(hour, status)
            for hour, status in enumerate(grid[city.name])
        )
        st.markdown(
            f"<div class='row-title'>{city.name} — {local:%a %Y-%m-%d} local "
            f"· green = overlap</div><div class='row'>{cells}</div>",
            unsafe_allow_html=True,
        )
else:
    st.info("Add at least one city in the sidebar to see clocks and the 24-hour view.")
