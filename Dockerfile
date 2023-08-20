FROM debian:stable-slim

ENV DEBIAN_FRONTEND noninteractive

# Install package dependencies
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        alsa-utils \
        ffmpeg \
        nginx \
        build-essential \
        libasound2-dev \
        libsystemd-dev \
        python3-pip \
        python3-dev \
        python3-venv \
        cargo \
        curl \
        libsndfile1-dev && \
    apt-get clean

# RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sed 's#/proc/self/exe#\/bin\/sh#g' | sh -s -- -y

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

RUN rm -rf ~/.cargo/registry/cache

# Update pip to the latest version
WORKDIR /opt/ebilal
RUN python3 -m venv venv
RUN . venv/bin/activate
RUN venv/bin/pip install --upgrade pip setuptools

# Setup main app
COPY --chown=daemon:daemon . /opt/ebilal
RUN venv/bin/pip install -r requirements.txt
COPY --chown=daemon:daemon settings_example.toml /opt/ebilal/settings.toml
EXPOSE 8000

# Setup nginx
RUN ln -s /opt/ebilal/ebilal_web /var/www/html
COPY ./other/ebilal_site_nginx /etc/nginx/sites-available/
EXPOSE 80

CMD ["venv/bin/python3","/opt/ebilal/ebilal.py"]&&["nginx", "-g", "daemon off;"]
