FROM resin/rpi-raspbian
USER root

RUN apt-get update && \
    apt-get -qy install ca-certificates python python-pip git ffplay && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get -qy clean all

RUN cd /opt/
RUN git clone git@bitbucket.org:mitpeople/ebilal.git
COPY config.json /opt/ebilal/
RUN cd ebilal
RUN pip install requirements.txt

CMD ["pythoni /opt/ebilal/livemasjidclient.py > /opt/ebilal/livemasjidclient.log 2>&1"]
