from dynaconf import LazySettings
from dynaconf.loaders.toml_loader import write
from fastapi import FastAPI
from typing import List
import alsaaudio
import uvicorn
from ebilal import LivemasjidClient

app = FastAPI()

class LivemasjidClientAPI:
    """Livemasjid client Object"""
    def __init__(self, client: LivemasjidClient):
        self.settings = LazySettings(settings_file="settings.toml")
        
        if self.settings.default.audio_device == "":
            try:
                self.mixer = alsaaudio.Mixer()
            except:
                self.mixer = alsaaudio.Mixer(alsaaudio.mixers()[0])
        else:
            self.mixer = alsaaudio.Mixer(self.settings.default.audio_device)
        self.current_vol = self.mixer.getvolume()[0]
        self.client = client

    @app.get("/mounts")
    def read_mounts(self):
        return self.settings.default.mounts


    @app.post("/mounts/{mount}")
    def set_mount(self,mount: str):
        self.settings.default.mounts = [mount]
        write('settings.toml', self.settings.to_dict(), merge=False)
        return {"mounts": self.settings.default.mounts}

    @app.post("/mounts/")
    def write_mounts(self,mounts: List[str]):
        self.settings.default.mounts = mounts
        write('settings.toml', self.settings.to_dict() , merge=False)
        return {"mounts": self.settings.default.mounts}

    @app.get("/server_url")
    def read_mounts(self):
        return self.settings.default.server_url

    @app.post("/server_url/")
    def write_url(self,url: str):
        self.settings.default.server_url = url
        write('settings.toml', self.settings.to_dict(), merge=True)
        return {"mounts": self.settings.default.server_url}

    @app.get("/volume")
    def read_root(self):
        return {"volume": self.mixer.getvolume()[0]}

    @app.post("/volume")
    def volset(self,vol:int):
        self.mixer.setvolume(vol)
        return {"volume": self.mixer.getvolume()}

    @app.post("/volume/up")
    def volup(self):
        if (mixer.getvolume()[0] <= 90):
            current_vol = mixer.getvolume()[0] + 10
            self.mixer.setvolume(current_vol)
        return {"volume": self.mixer.getvolume()}

    @app.post("/volume/down")
    def volup(self):
        if (mixer.getvolume()[0] >= 10):
            current_vol = mixer.getvolume()[0] - 10
            self.mixer.setvolume(current_vol)
        return {"volume": self.mixer.getvolume()}

    def runServer(self):
        uvicorn.run("ebilal_api:app",host='0.0.0.0', port=8000, reload=True, debug=True, workers=3)

if __name__=="__main__":
    uvicorn.run("ebilal_api:app",host='0.0.0.0', port=8000, reload=True, debug=True, workers=3)
