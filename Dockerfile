FROM balenalib/raspberry-pi-debian-python
USER root

RUN apt-get update && \
    apt-get -qy install ca-certificates python3 python3-pip git ffmpeg && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get -qy clean all

RUN cd /opt/ && git clone https://yusuf_kaka@bitbucket.org/mitpeople/ebilal.git && cd ebilal && pip3 install -r ./requirements.txt

ENTRYPOINT ["python","/opt/ebilal/livemasjidclient.py"]
