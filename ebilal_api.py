from dynaconf import LazySettings
from dynaconf.loaders.json_loader import write
from fastapi import FastAPI
from typing import List

settings = LazySettings(settings_file="config.json")

app = FastAPI()

@app.get("/settings")
def read_root():
    return settings.default

@app.get("/mounts")
def read_mounts():
    return settings.default.mounts

@app.post("/mounts/")
def write_mounts(mounts: List[str]):
    write('config.json', {"DEFAULT": {"MOUNTS": mounts}}, merge=True)
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