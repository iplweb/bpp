#!/bin/bash

pg_dumpall --globals-only > postgresql-globals.sql
pg_dump -Fc $DATABASE_NAME > postgresql-$DATABASE_NAME.sql

tar czvf mediaroot.tgz /mediaroot

rclone sync . backup_enc:`date +%Y-%m`/`date +%d`/
