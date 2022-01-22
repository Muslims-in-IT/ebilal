from dynaconf import LazySettings
from dynaconf.loaders.toml_loader import write
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import alsaaudio
import uvicorn
from ebilal import LivemasjidClient

app = FastAPI(root_path="/api")

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = LazySettings(settings_file="/opt/ebilal/settings.toml")

if settings.default.audio_device == "":
    try:
        mixer = alsaaudio.Mixer()
    except:
        mixer = alsaaudio.Mixer(alsaaudio.mixers()[0])
else:
    mixer = alsaaudio.Mixer(settings.default.audio_device)
current_vol = mixer.getvolume()[0]

@app.get("/mounts")
def read_mounts():
    return {"mounts": settings.default.mounts}


@app.post("/mounts/{mount}")
def set_mount(mount: str):
    settings.default.mounts = [mount]
    write('settings.toml', settings.to_dict(), merge=False)
    return {"mounts": settings.default.mounts}

@app.post("/mounts")
def write_mounts(mounts: List[str]):
    settings.default.mounts = mounts
    write('settings.toml', settings.to_dict() , merge=False)
    return {"mounts": settings.default.mounts}

@app.get("/server_url")
def read_mounts():
    return {"server_url": settings.default.server_url}

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

if __name__=="__main__":
    uvicorn.run("ebilal_api:app",host='0.0.0.0', port=8000, reload=True, debug=True, workers=3)
