from dynaconf import LazySettings
from dynaconf.loaders.toml_loader import write
from fastapi import FastAPI
from typing import List
import alsaaudio

settings = LazySettings(settings_file="settings.toml")

app = FastAPI()
if settings.default.audio_device == "":
    mixer = alsaaudio.Mixer()
else:
    mixer = alsaaudio.Mixer(settings.default.audio_device)
current_vol = mixer.getvolume()[0]

@app.get("/mounts")
def read_mounts():
    return settings.default.mounts


@app.post("/mounts/{mount}")
def set_mount(mount: str):
    settings.default.mounts = [mount]
    write('settings.toml', settings.to_dict(), merge=False)
    return {"mounts": settings.default.mounts}

@app.post("/mounts/")
def write_mounts(mounts: List[str]):
    settings.default.mounts = mounts
    write('settings.toml', settings.to_dict() , merge=False)
    return {"mounts": settings.default.mounts}

@app.get("/server_url")
def read_mounts():
    return settings.default.server_url

@app.post("/server_url/")
def write_url(url: str):
    settings.default.server_url = url
    write('settings.toml', settings.to_dict(), merge=True)
    return {"mounts": settings.default.server_url}

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

""" 
@app.get("/settings")
def read_root():
    return settings.default

@app.get("/settings/{setting_name}")
def read_item(setting_name: str):
    return {setting_name: settings["default."+setting_name]}

@app.put("/settings/{setting_name}")
def write_item(setting_name: str,setting_value: str):
    write('settings.toml', {"DEFAULT": {setting_name: setting_value}}, merge=True)
    return {setting_name: settings["default."+setting_name]} """
