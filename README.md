# TrajectoryLens

TrajectoryLens analyzes coding-agent runs (terminal task trajectories), shows where and why the agent failed, and groups failures into recurring types.

The backend stores trajectories in SQLite and the frontend shows the health check.

`POST /runs` stores a trajectory (201, 409 when `run_id` already exists, 422 when the body is invalid). `GET /runs` lists runs, newest first, with optional `status`, `model`, `limit` (default 50, max 100), and `offset`. `GET /runs/{run_id}` returns one run and its steps. `DELETE /runs/{run_id}` deletes the run and its steps. `POST /runs/{run_id}/analyze` replaces stored findings. `GET /runs/{run_id}/findings` returns them.

The database file is `backend/trajectorylens.db` unless `TRAJECTORYLENS_DATABASE_URL` is set.

Synthetic samples, with a fixed seed:

```bash
python scripts/generate_samples.py
python scripts/load_samples.py
python scripts/generate_heldout.py
```

`expected_findings` stays in the JSON file and is not sent to the API. The held-out file is a separate 15-run set used only to print precision and recall.

## Prerequisites

- Python 3.11
- Node.js 20 or newer (with npm)

## Backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

Checks:

```bash
cd backend
source .venv/bin/activate
ruff check .
mypy app
pytest -q
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The page calls `GET /health` through the Vite dev proxy and shows the backend status (`ok`).

Build check:

```bash
cd frontend
npx tsc --noEmit
npm run build
```
