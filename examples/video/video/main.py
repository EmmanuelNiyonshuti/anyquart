from pathlib import Path

from anyquart import AnyQuart
from anyquart import render_template
from anyquart import send_file

app = AnyQuart(__name__)


@app.get("/")
async def index():
    return await render_template("index.html")


@app.route("/video.mp4")
async def auto_video():
    res = await send_file(Path(app.static_folder) / "video.mp4", conditional=True)
    return res


def run() -> None:
    app.run()
