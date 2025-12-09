import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Resolve the SQLite database location.
# - Defaults to a file named "todo.db" at the repo root (three directories up from this file).
# - Can be overridden using the SQLITE_DB environment variable.
DB_FILE = os.getenv(
    "SQLITE_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "todo.db"),
)

# Ensure the target directory exists (especially if SQLITE_DB points to a nested path).
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)


@contextmanager
def get_conn():
    """
    Context manager to get a SQLite connection with proper row factory.
    Ensures the connection is closed automatically.

    Why a context manager?
    - Guarantees commit/close behavior even when exceptions occur.
    - Keeps connection handling consistent across endpoints.
    - Row factory returns rows accessible by column name, improving readability.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()  # commit automatically after successful operations
    finally:
        conn.close()  # always close to avoid connection leaks


def init_db():
    """
    Initialize the SQLite database and create the tasks table if it doesn't exist.
    This function is idempotent and safe to run on every startup.

    Schema notes:
    - completed is stored as INTEGER (0/1) for simplicity with sqlite3.
    - created_at is ISO8601 text to keep ordering consistent with datetime() in SQL.
    """
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )


# PUBLIC_INTERFACE
class TaskCreate(BaseModel):
    """Payload for creating a new task."""
    # Title is required and trimmed on write; validated to have at least one non-empty character.
    title: str = Field(..., description="Title of the task", min_length=1, max_length=255)
    # Clients may optionally set completed at creation; default is False.
    completed: Optional[bool] = Field(default=False, description="Completion status of the task (default false)")


# PUBLIC_INTERFACE
class TaskUpdate(BaseModel):
    """Payload for updating an existing task."""
    # Either field is optional; at least one must be provided or a 400 is returned.
    title: Optional[str] = Field(default=None, description="Updated title for the task", min_length=1, max_length=255)
    completed: Optional[bool] = Field(default=None, description="Updated completion status")


# PUBLIC_INTERFACE
class Task(BaseModel):
    """Task model returned by the API."""
    # API response model with types and descriptions for Swagger/OpenAPI docs.
    id: int = Field(..., description="Unique identifier for the task")
    title: str = Field(..., description="Title of the task")
    completed: bool = Field(..., description="Completion status of the task")
    created_at: str = Field(..., description="ISO timestamp when the task was created")


def row_to_task(row: sqlite3.Row) -> Task:
    """Convert a SQLite row to Task model.

    This isolates conversion logic and ensures consistency across endpoints.
    """
    return Task(
        id=row["id"],
        title=row["title"],
        completed=bool(row["completed"]),  # normalize INTEGER 0/1 to boolean
        created_at=row["created_at"],
    )


app = FastAPI(
    title="Todo Backend API",
    description="A simple FastAPI backend providing CRUD endpoints for a todo application with SQLite persistence.",
    version="1.0.0",
    openapi_tags=[
        {"name": "health", "description": "Health check endpoints"},
        {"name": "tasks", "description": "Operations on todo tasks"},
    ],
)

# CORS configuration: allow frontend at localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Note: Expand allowlist if your frontend runs on a different origin.
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Initialize the database on startup.

    This ensures the tasks table exists before the first request hits the API.
    """
    init_db()


# PUBLIC_INTERFACE
@app.get("/health", tags=["health"], summary="Health check", description="Simple health check endpoint.")
def health_check():
    """
    Health check endpoint.

    Returns:
        JSON containing a status message.
    """
    try:
        return {"status": "ok"}
    except HTTPException:
        # Pass through known HTTP exceptions
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}")


# PUBLIC_INTERFACE
@app.get("/tasks", response_model=List[Task], tags=["tasks"], summary="List all tasks", description="Retrieve all tasks sorted by creation time descending.")
def list_tasks() -> List[Task]:
    """
    List all tasks.

    Returns:
        A list of Task objects.
    """
    try:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT id, title, completed, created_at FROM tasks ORDER BY datetime(created_at) DESC"
            ).fetchall()
            return [row_to_task(r) for r in rows]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}")


# PUBLIC_INTERFACE
@app.post("/tasks", response_model=Task, status_code=201, tags=["tasks"], summary="Create a new task", description="Create a new task with a title and optional completed flag (default false).")
def create_task(payload: TaskCreate) -> Task:
    """
    Create a new task.

    Args:
        payload: TaskCreate with title and optional completed.

    Returns:
        The created Task.
    """
    try:
        created_at = datetime.utcnow().isoformat()
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO tasks (title, completed, created_at) VALUES (?, ?, ?)",
                (payload.title.strip(), 1 if payload.completed else 0, created_at),
            )
            task_id = cur.lastrowid
            row = conn.execute(
                "SELECT id, title, completed, created_at FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return row_to_task(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}")


# PUBLIC_INTERFACE
@app.put(
    "/tasks/{task_id}",
    response_model=Task,
    tags=["tasks"],
    summary="Update a task",
    description="Update the title and/or completion status of an existing task.",
)
def update_task(
    payload: TaskUpdate,
    task_id: int = Path(..., description="ID of the task to update"),
) -> Task:
    """
    Update an existing task.

    Args:
        payload: Fields to update (title, completed).
        task_id: Task ID path parameter.

    Returns:
        The updated Task.

    Raises:
        HTTPException 404 if task not found.
        HTTPException 400 if no fields provided.
    """
    try:
        if payload.title is None and payload.completed is None:
            raise HTTPException(status_code=400, detail="No fields provided to update")

        with get_conn() as conn:
            existing = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Task not found")

            # Build dynamic update
            sets = []
            values = []
            if payload.title is not None:
                sets.append("title = ?")
                values.append(payload.title.strip())
            if payload.completed is not None:
                sets.append("completed = ?")
                values.append(1 if payload.completed else 0)
            values.append(task_id)

            conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", tuple(values))
            row = conn.execute(
                "SELECT id, title, completed, created_at FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return row_to_task(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}")


# PUBLIC_INTERFACE
@app.patch(
    "/tasks/{task_id}/toggle",
    response_model=Task,
    tags=["tasks"],
    summary="Toggle completion",
    description="Toggle the completed status of a task.",
)
def toggle_task(
    task_id: int = Path(..., description="ID of the task to toggle"),
) -> Task:
    """
    Toggle the completed status for a task.

    Args:
        task_id: Task ID path parameter.

    Returns:
        The updated Task.

    Raises:
        HTTPException 404 if task not found.
    """
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT id, title, completed, created_at FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Task not found")

            new_completed = 0 if bool(row["completed"]) else 1
            conn.execute("UPDATE tasks SET completed = ? WHERE id = ?", (new_completed, task_id))
            row = conn.execute(
                "SELECT id, title, completed, created_at FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return row_to_task(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}")


# PUBLIC_INTERFACE
@app.delete(
    "/tasks/{task_id}",
    status_code=204,
    tags=["tasks"],
    summary="Delete a task",
    description="Delete an existing task by its ID.",
)
def delete_task(
    task_id: int = Path(..., description="ID of the task to delete"),
):
    """
    Delete a task.

    Args:
        task_id: Task ID path parameter.

    Returns:
        Empty response with status code 204.

    Raises:
        HTTPException 404 if task not found.
    """
    try:
        with get_conn() as conn:
            res = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            if res.rowcount == 0:
                raise HTTPException(status_code=404, detail="Task not found")
        return None
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}")
