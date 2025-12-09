# simple-todo-list-185425-185434

A simple full-stack Todo application consisting of:
- Backend: FastAPI service that exposes REST endpoints and persists data in SQLite.
- Frontend: React web app (separate container) that consumes the backend API.
- Database: SQLite database file stored locally.

This repository contains the backend service. The frontend lives in its own container/workspace.

## Repository Structure

- todo_backend/
  - requirements.txt — Python dependencies for FastAPI service
  - .env.example — Example environment variables for backend configuration
  - interfaces/openapi.json — Generated OpenAPI spec for the backend API
  - src/api/
    - main.py — FastAPI app: routes, models, SQLite DB initialization
    - generate_openapi.py — Script to generate/refresh `interfaces/openapi.json`

## Backend (FastAPI + SQLite)

### Features
- Health check endpoint: GET /health
- Tasks CRUD:
  - GET /tasks — list all tasks
  - POST /tasks — create a new task
  - PUT /tasks/{id} — update task title and/or completed
  - PATCH /tasks/{id}/toggle — toggle completion state
  - DELETE /tasks/{id} — delete a task
- CORS configured to allow http://localhost:3000 (and 127.0.0.1:3000)
- Automatic SQLite DB initialization on startup
- OpenAPI/Swagger docs at /docs

### Data Model
- Task:
  - id: integer (auto-increment)
  - title: string (required)
  - completed: boolean (default false)
  - created_at: ISO timestamp

### Setup

1) Python version
- Recommended: Python 3.10+ (FastAPI/Pydantic compatible)

2) Install dependencies
- Create/activate a virtual environment (recommended), then:
  pip install -r todo_backend/requirements.txt

3) Optional environment configuration
- Copy `.env.example` to `.env` (same folder as requirements.txt) if you want to customize:
  - SQLITE_DB — custom path to SQLite DB file (default is `<repo_root>/todo.db`)

### Running the Backend

From the `todo_backend` folder (or repo root), run:

- Using uvicorn directly:
  uvicorn src.api.main:app --host 0.0.0.0 --port 3001 --reload

- Once running:
  - Health: http://localhost:3001/health
  - Docs: http://localhost:3001/docs
  - OpenAPI JSON: http://localhost:3001/openapi.json

The SQLite database is initialized automatically on first start. By default it is created at `<repo_root>/todo.db`. If you set `SQLITE_DB` in the environment, the app will use that path.

### CORS

CORS is enabled for:
- http://localhost:3000
- http://127.0.0.1:3000

This allows the React frontend (running on port 3000) to access the API.

### API Summary

- GET /health
  - Returns: {"status": "ok"}
- GET /tasks
  - Returns: [Task]
- POST /tasks
  - Body: { "title": "string", "completed": false }
  - Returns: Task (201)
- PUT /tasks/{id}
  - Body: { "title"?: "string", "completed"?: boolean }
  - Returns: Task
- PATCH /tasks/{id}/toggle
  - Returns: Task (completed toggled)
- DELETE /tasks/{id}
  - Returns: 204 No Content

Pydantic models:
- TaskCreate(title, completed=false)
- TaskUpdate(title?, completed?)
- Task(id, title, completed, created_at)

### Generating OpenAPI Spec

If you need to regenerate the static `interfaces/openapi.json`:
- Ensure the app code is importable, then run:
  python -m src.api.generate_openapi

This writes a fresh schema to `todo_backend/interfaces/openapi.json`.

### Notes

- Do not commit a `.env` file to version control. Use `.env.example` as a reference.
- The backend is designed to be consumed by the React frontend at port 3000.
- Make sure the selected port (3001) is available when starting the backend.

### Architecture and Code Guide

- src/api/main.py
  - Defines the FastAPI app and all routes under a simple, flat module to keep the example approachable.
  - Uses Python's built-in sqlite3 library with a context manager for safe transaction handling.
  - Initializes the DB on startup via the FastAPI lifecycle hook to ensure tables exist before requests are served.
  - Endpoints are wrapped in try/except blocks:
    - HTTPException is re-raised as-is to preserve status codes like 400/404.
    - Unexpected exceptions are mapped to a 500 with a concise message, to avoid leaking stack traces.
  - CORS is restricted to http://localhost:3000 and http://127.0.0.1:3000 to support local frontend development.

- src/api/generate_openapi.py
  - Imports the FastAPI app and writes its generated OpenAPI schema to interfaces/openapi.json.
  - Can be run any time the API changes to refresh the interface description.

- Database
  - The DB file defaults to <repo_root>/todo.db.
  - You can set SQLITE_DB in the environment to point to a different file path if desired.

### Development Tips

- Linting: a flake8 dependency is included; you can run flake8 in the backend folder.
- Testing: pytest is included; you can add tests under a tests/ directory in todo_backend and run pytest.
- Docs: Use the built-in Swagger UI at /docs for exploration and manual verification.
