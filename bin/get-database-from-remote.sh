#!/bin/bash -e

# Pobiera dump bazy danych ze zdalnego serwera i uruchamia procedurę
# odtworz.sh; do tego wczesniej zapisuje baze danych w $OUTDIR

OUTDIR=~/Programowanie/bazy
DBNAME=bpp

TIMESTAMP=`date +%s`
FILENAME=dump-$TIMESTAMP.pgdump
FN=/tmp/$FILENAME
SAVE_AS="$OUTDIR/$1_$FILENAME"

ssh $1 -- "mkdir $FN && pg_dump -j 4 -v -Fd $DBNAME --file=$FN"
scp -r $1:$FN $FN
ssh $1 -- rm -r $FN

BASEDIR=$(dirname "$0")
$BASEDIR/odtworz.sh $FN
mv $FN $SAVE_AS

echo "Zapisano dump jako $SAVE_AS"
du -h "$SAVE_AS"
# rm -r $FN
