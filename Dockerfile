FROM balenalib/raspberry-pi-python

RUN [ "cross-build-start" ]

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

RUN install_packages ffmpeg nginx

# Install pip requirements
RUN pip3 install --upgrade pip
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# Setup main app
WORKDIR /opt/ebilal
COPY . /opt/ebilal
COPY settings_example.toml /opt/ebilal/settings.toml
EXPOSE 8000

# Setup nginx
RUN ln -s /opt/ebilal/ebilal_web /var/www/html
COPY other/ebilal_site_nginx /etc/nginx/sites-available/
EXPOSE 80

CMD ["python3","/opt/ebilal/ebilal.py"]&&["nginx", "-g", "daemon off;"]

RUN [ "cross-build-end" ]