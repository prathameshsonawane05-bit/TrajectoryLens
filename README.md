# TrajectoryLens

TrajectoryLens analyzes coding-agent runs (terminal task trajectories), shows where and why the agent failed, and groups failures into recurring types.

This repository is at stage 1: the backend exposes a health check, and the frontend displays it.

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
