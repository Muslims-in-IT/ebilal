FROM balenalib/raspberrypi3-python

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

RUN install_packages wget git ffmpeg ssh-client build-essential libsystemd-dev

# Install pip requirements
RUN pip3 install --upgrade pip
COPY requirements.txt .
RUN pip3 install -r requirements.txt

WORKDIR /opt/ebilal
COPY . /opt/ebilal
COPY settings_example.toml /opt/ebilal/settings.toml

CMD ["python3","/opt/ebilal/ebilal.py"]