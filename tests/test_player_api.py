"""Tests for the playlist ordering, pinning API and the shared config store."""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SETTINGS = '''[DEFAULT]
server_url = "http://livemasjid.com:8000/"
mounts = [ "greensidemasjid",]
audio_device = ""
loglevel = "INFO"
pimoroni = false
volume = 80
'''


@pytest.fixture()
def app_mod(tmp_path, monkeypatch):
    path = tmp_path / "settings.toml"
    path.write_text(SETTINGS)
    monkeypatch.setenv("EBILAL_SETTINGS", str(path))
    # (re)import with the temp settings file
    sys.modules.pop("ebilal", None)
    import ebilal
    yield ebilal
    sys.modules.pop("ebilal", None)


@pytest.fixture()
def client(app_mod):
    from fastapi.testclient import TestClient
    return TestClient(app_mod.app)


def feed(player, states):
    for mount, st in states.items():
        player.mounts[mount] = st


def test_pinned_defaults_to_quran_when_unset(client):
    assert client.get("/pinned").json() == {"pinned": ["activestream"]}


def test_unpin_all_is_remembered_not_reset_to_default(client):
    client.post("/pinned", json={"pinned": []})
    assert client.get("/pinned").json() == {"pinned": []}


def test_pin_any_feed_keeps_order_and_dedupes(client):
    r = client.post("/pinned", json={"pinned": ["makkah", "activestream", "makkah"]})
    assert r.json() == {"pinned": ["makkah", "activestream"]}
    assert client.get("/pinned").json()["pinned"] == ["makkah", "activestream"]


def test_favourites_and_pins_do_not_clobber_each_other(client, app_mod):
    client.post("/favourites", json={"favourites": ["a", "b"]})
    client.post("/pinned", json={"pinned": ["makkah"]})
    client.post("/volume?volume=33")
    client.post("/favourites", json={"favourites": ["a"]})  # removal must really remove
    assert client.get("/favourites").json() == {"favourites": ["a"]}
    assert client.get("/pinned").json() == {"pinned": ["makkah"]}
    assert client.get("/volume").json() == {"volume": 33}


def test_playlist_autoplay_first_and_no_mp3_twins(app_mod):
    p = app_mod.livemasjid
    feed(p, {"zeta": "started", "makkah": "started", "makkah.mp3": "started",
             "activestream": "started", "activestream.mp3": "started",
             "quiet": "stopped"})
    p.mountToPlay = ["makkah", "zeta"]
    assert p.playlist() == ["makkah", "zeta", "activestream"]


def test_pins_do_not_affect_skip_order(app_mod):
    p = app_mod.livemasjid
    feed(p, {"a": "started", "b": "started"})
    p.mountToPlay = []
    app_mod.config.update(pinned=["b"])
    assert p.playlist() == ["a", "b"]


def test_liked_but_offline_is_not_in_playlist(app_mod):
    p = app_mod.livemasjid
    feed(p, {"zeta": "started", "fav": "stopped"})
    p.mountToPlay = ["fav"]
    assert p.playlist() == ["zeta"]


def test_step_walks_and_wraps(app_mod, monkeypatch):
    p = app_mod.livemasjid
    played = []
    monkeypatch.setattr(p, "playmount", lambda m: (played.append(m), setattr(p, "playing", m)))
    feed(p, {"a": "started", "b": "started", "c": "started"})
    p.mountToPlay = []
    p.playing = "a"
    assert p.step(+1) == "b"
    assert p.step(+1) == "c"
    assert p.step(+1) == "a"
    assert p.step(-1) == "c"


def test_step_with_nothing_live_returns_none(app_mod):
    assert app_mod.livemasjid.step(+1) is None
    assert app_mod.livemasjid.toggle() is None


def test_volume_nudge_is_deferred_then_persisted(app_mod):
    import time
    p = app_mod.livemasjid
    p.VOLUME_COMMIT_DELAY = 0.05
    p.volume = 50
    p.nudge_volume(+5)
    p.nudge_volume(+5)
    assert p.volume == 60
    assert app_mod.config.get("volume") == 80  # nothing written yet
    time.sleep(0.2)
    assert app_mod.config.get("volume") == 60  # committed once


def test_stopped_message_for_other_mount_does_not_silence_player(app_mod, monkeypatch):
    p = app_mod.livemasjid
    stops = []
    monkeypatch.setattr(p, "stop", lambda: stops.append(1))
    p.mountToPlay = ["fav"]
    p.playing = "something_else"

    class Msg:
        topic = "mounts/fav"
        payload = b"stopped"
    p.on_message(None, None, Msg)
    assert stops == []
