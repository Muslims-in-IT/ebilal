FROM balenalib/raspberry-pi-debian-python
USER root

RUN apt-get update && \
    apt-get -qy install ca-certificates python python-pip git ffmpeg ssh-client && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get -qy clean all

RUN cd /opt/
RUN git clone git@bitbucket.org:mitpeople/ebilal.git
RUN cd ebilal
RUN pip install requirements.txt

ENTRYPOINT ["python","/opt/ebilal/livemasjidclient.py"]
