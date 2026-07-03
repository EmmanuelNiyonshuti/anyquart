from pathlib import Path

import aiosqlite

from anyquart import AnyQuart
from anyquart import g
from anyquart import redirect
from anyquart import render_template
from anyquart import request
from anyquart import url_for

app = AnyQuart(__name__)

app.config.update(
    {
        "DATABASE": Path(app.root_path) / "blog.db",
    }
)


async def _connect_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(app.config["DATABASE"])
    db.row_factory = aiosqlite.Row
    return db


async def _get_db() -> aiosqlite.Connection:
    if not hasattr(g, "sqlite_db"):
        g.sqlite_db = await _connect_db()
    return g.sqlite_db


@app.teardown_appcontext
async def close_db(exception=None):
    db = g.pop("sqlite_db", None)
    if db is not None:
        await db.close()


@app.get("/")
async def posts() -> str:
    db = await _get_db()
    cur = await db.execute(
        """SELECT title, text
             FROM post
         ORDER BY id DESC""",
    )
    posts = await cur.fetchall()
    await cur.close()
    return await render_template("posts.html", posts=posts)


@app.route("/create/", methods=["GET", "POST"])
async def create() -> str:
    if request.method == "POST":
        db = await _get_db()
        form = await request.form
        await db.execute(
            "INSERT INTO post (title, text) VALUES (?, ?)",
            [form["title"], form["text"]],
        )
        await db.commit()
        return redirect(url_for("posts"))
    else:
        return await render_template("create.html")


async def init_db() -> None:
    db = await _connect_db()
    with open(Path(app.root_path) / "schema.sql") as file_:
        await db.executescript(file_.read())
    await db.commit()
    await db.close()


def run() -> None:
    app.run()
