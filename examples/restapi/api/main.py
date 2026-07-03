from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from anyquart import AnyQuart
from anyquart import jsonify
from anyquart import request

app = AnyQuart(__name__)


class TodoIn(BaseModel):
    task: str
    due: datetime | None = None


class Todo(TodoIn):
    id: int


@app.post("/echo")
async def echo() -> dict[str, Any]:
    data = await request.get_json()
    return {"input": data, "extra": True}


@app.post("/todos/")
async def create_todo():
    data = await request.get_json()
    todo_in = TodoIn(**data)
    todo = Todo(id=1, task=todo_in.task, due=todo_in.due)
    return jsonify(todo.model_dump()), 201


def run() -> None:
    app.run()
