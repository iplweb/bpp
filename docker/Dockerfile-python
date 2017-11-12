FROM python:3.6

LABEL "com.example.vendor"="iplweb.pl"
LABEL version="0.1"

RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    software-properties-common \
    build-essential \
    python3-dev \
    libssl-dev \
    libffi-dev \
    git \
    gettext 
