FROM balenalib/raspberry-pi-debian-python
RUN [ "cross-build-start" ]
USER root

EXPOSE 8000

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get -qy install ca-certificates build-essential git ffmpeg python3-dev libasound2-dev python3 python3-pip ssh-client libsystemd-dev && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get -qy clean all

# Install pip requirements
COPY requirements.txt .
RUN python3 -m pip install -r requirements.txt

WORKDIR /opt/ebilal
COPY . /opt/ebilal

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker", "ebilal_api:app"] && ["python3","/opt/ebilal/ebi]al.py"]

RUN [ "cross-build-end" ]