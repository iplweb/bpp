#!/bin/bash

pg_ctlcluster 10 main start

echo "CREATE COLLATION "pl_PL"(locale='pl_PL.utf8')" | su - postgres -c psql template1

tail -f /var/log/postgresql/*
