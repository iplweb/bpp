#!/bin/bash -e

# Pobiera dump bazy danych ze zdalnego serwera i uruchamia procedurę
# odtworz.sh

TIMESTAMP=`date +%s`
DBNAME=bpp
FN=/tmp/dump-$TIMESTAMP.pgdump

ssh $1 -- "mkdir $FN && pg_dump -j 4 -v -Fd $DBNAME --file=$FN"
scp -r $1:$FN $FN
ssh $1 -- rm -r $FN

BASEDIR=$(dirname "$0")
$BASEDIR/odtworz.sh $FN
rm -r $FN
