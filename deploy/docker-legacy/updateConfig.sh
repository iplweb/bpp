#!/usr/bin/env bash
# https://stackoverflow.com/questions/30848670/how-to-customize-the-configuration-file-of-the-official-postgresql-docker-image

cat /tmp/postgresql.conf >> /var/lib/postgresql/data/postgresql.conf
