FROM balenalib/raspberry-pi-debian-python
RUN [ "cross-build-start" ]
USER root

RUN apt-get update && \
    apt-get -qy install ca-certificates build-essential git ffmpeg python3-dev libasound2-dev && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get -qy clean all
RUN pip3 install --upgrade pip
RUN cd /opt/ && git clone https://yusuf_kaka@bitbucket.org/mitpeople/ebilal.git && cd ebilal && pip3 install -r ./requirements.txt
ENTRYPOINT ["python3","/opt/ebilal/livemasjidclient.py"]
RUN [ "cross-build-end" ]
