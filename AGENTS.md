# AGENTS.md

## Repo state

- Spec-first project: read `SPEC.md` before touching code — it defines working hours, the whole-hour overlap rule, and the 36-city catalog. UI mock: `ui-design.png`.
- Code so far: `logic.py` (pure time logic, **no Streamlit imports**) + `test_logic.py`. Streamlit UI (`app.py`) not written yet. No git, no lint/typecheck config.
- Run tests: `.venv\Scripts\pytest.exe -q` (expect all green before/after changes).

## Python environment (verified)

- `.venv/` is a Python **3.10.11** venv (Windows, `venv` layout). It is not committed to any VCS (no `.git` exists).
- Activate before running anything:
  - PowerShell: `.venv\Scripts\Activate.ps1`
  - cmd: `.venv\Scripts\activate.bat`
- Do not create a second venv or upgrade Python without asking.

## Installed stack (from `site-packages`, no manifest exists)

- Web/app: `streamlit` (1.65), `starlette` + `uvicorn` + `websockets`, `python-multipart`
- Data: `pandas`, `numpy`, `pyarrow`, `pillow`
- Testing: `pytest` (9.1) — available as `.venv\Scripts\pytest.exe`
- Note: `starlette`/`uvicorn` are present but **`fastapi` is not installed** — don't assume FastAPI.

## Before installing dependencies

- There is no `requirements.txt` / `pyproject.toml` yet. When adding the first real dependency file, generate it from what is already in `.venv` (e.g. `pip freeze > requirements.txt`) so the existing environment stays reproducible.
