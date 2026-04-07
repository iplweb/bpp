FROM ubuntu:22.04

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=apt-cache \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked,id=apt-lists \
    apt update && apt install -y postgresql-client wget busybox unzip && \
    wget -q https://downloads.rclone.org/v1.68.0/rclone-v1.68.0-linux-amd64.zip -O /tmp/rclone.zip && \
    unzip -q /tmp/rclone.zip -d /tmp && \
    mv /tmp/rclone-v1.68.0-linux-amd64/rclone /usr/local/bin/ && \
    chmod +x /usr/local/bin/rclone && \
    rm -rf /tmp/rclone.zip /tmp/rclone-v1.68.0-linux-amd64

COPY run_backup.sh /
