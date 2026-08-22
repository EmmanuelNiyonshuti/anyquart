from __future__ import annotations

from datetime import datetime
from typing import Any

from anyquart_pydantic import AnyQuartPydantic
from pydantic import BaseModel

from anyquart import AnyQuart
from anyquart import request

app = AnyQuart(__name__)
AnyQuartPydantic(app)


class Todo(BaseModel):
    task: str
    due: datetime | None = None


class TodoOut(Todo):
    id: int


@app.post("/echo")
async def echo() -> dict[str, Any]:
    data = await request.get_json()
    return {"input": data, "extra": True}


@app.post("/todos/")
async def create_todo(todo: Todo) -> TodoOut:
    new_todo = TodoOut(task=todo.task, due=todo.due, id=1)

    return new_todo, 201


def run() -> None:
    app.run()
