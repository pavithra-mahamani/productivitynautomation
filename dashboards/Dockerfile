FROM ubuntu:latest
ENV DEBIAN_FRONTEND "noninteractive"
RUN apt-get update -y && apt-get install -y python3-dev python3-pip python3-setuptools cmake build-essential
RUN mkdir /app
COPY ./requirements.txt /app
WORKDIR /app
RUN pip3 install -r requirements.txt
COPY ./dashboard.py /app
COPY ./entrypoint.sh /app

ENTRYPOINT ["./entrypoint.sh"]