#!/bin/bash

pg_ctlcluster 9.6 main start

psql "CREATE COLLATION IF NOT EXISTS pl_PL(locale='pl_PL.utf8');" | psql template1

tail -f /var/log/postgresql/*
