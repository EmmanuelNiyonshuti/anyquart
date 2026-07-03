import pytest


@pytest.mark.anyio
async def test_auto_video(test_client) -> None:
    response = await test_client.get("/video.mp4")
    data = await response.get_data()
    assert len(data) == 255_849

    response = await test_client.get("/video.mp4", headers={"Range": "bytes=200-1000"})
    data = await response.get_data()
    assert len(data) == 801
