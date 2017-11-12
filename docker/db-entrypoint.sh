#!/bin/bash

pg_ctlcluster 9.6 main start

tail -f /var/log/postgresql/*
