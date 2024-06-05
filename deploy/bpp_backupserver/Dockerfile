FROM ubuntu:22.04

RUN apt update && apt install -y postgresql-client curl busybox

RUN curl https://rclone.org/install.sh | bash

COPY run_backup.sh /
