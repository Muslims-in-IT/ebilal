from dynaconf import LazySettings
from dynaconf.loaders.json_loader import write
from fastapi import FastAPI
from typing import List
import alsaaudio

settings = LazySettings(settings_file="config.json")

app = FastAPI()
mixer = alsaaudio.Mixer()
current_vol = mixer.getvolume()[0]

@app.get("/settings")
def read_root():
    return settings.default

@app.get("/mounts")
def read_mounts():
    return settings.default.mounts

@app.post("/mounts/")
def write_mounts(mounts: List[str]):
    settings.default.mounts = mounts
    write('config.json', settings, merge=False)
    return {"mounts": settings.default.mounts}

@app.get("/server_url")
def read_mounts():
    return settings.default.server_url

@app.post("/server_url/")
def write_url(url: str):
    write('config.json', {"DEFAULT": {"SERVER_URL": url}}, merge=True)
    return {"mounts": settings.default.server_url}

@app.get("/settings/{setting_name}")
def read_item(setting_name: str):
    return {setting_name: settings["default."+setting_name]}

@app.put("/settings/{setting_name}")
def write_item(setting_name: str,setting_value: str):
    write('config.json', {"DEFAULT": {setting_name: setting_value}}, merge=True)
    return {setting_name: settings["default."+setting_name]}

@app.get("/volume")
def read_root():
    return {"volume": mixer.getvolume()[0]}

@app.post("/volume")
def volset(vol:int):
    mixer.setvolume(vol)
    return {"volume": mixer.getvolume()}

@app.post("/volume/up")
def volup():
    if (mixer.getvolume()[0] <= 90):
        current_vol = mixer.getvolume()[0] + 10
        mixer.setvolume(current_vol)
    return {"volume": mixer.getvolume()}

@app.post("/volume/down")
def volup():
    if (mixer.getvolume()[0] >= 10):
        current_vol = mixer.getvolume()[0] - 10
        mixer.setvolume(current_vol)
    return {"volume": mixer.getvolume()}
