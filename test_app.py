"""App-level acceptance tests for app.py (SPEC.md §3)."""

from streamlit.testing.v1 import AppTest


def run_app(selection: list[str] | None = None) -> AppTest:
    at = AppTest.from_file("app.py", default_timeout=20).run()
    if selection is not None:
        at.sidebar.multiselect[0].set_value(selection).run()
    return at


def test_warning_when_no_overlap():
    at = run_app(["Tokyo", "London"])
    assert not at.exception
    assert len(at.warning) == 1
    assert "no overlapping hours" in at.warning[0].value.lower()


def test_no_warning_when_overlap_exists():
    at = run_app()  # default London + Bali -> 5.0 h
    assert not at.exception
    assert len(at.warning) == 0


def test_no_warning_when_no_cities():
    at = run_app([])
    assert not at.exception
    assert len(at.warning) == 0
    assert len(at.info) == 1
