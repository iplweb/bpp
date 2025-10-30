FROM ubuntu:22.04

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt update && apt install -y postgresql-client curl busybox

RUN curl https://rclone.org/install.sh | bash

COPY run_backup.sh /
