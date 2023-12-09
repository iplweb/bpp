#!/bin/bash -e

# Pobiera dump bazy danych ze zdalnego serwera i uruchamia procedurę
# odtworz.sh; do tego wczesniej zapisuje baze danych w $OUTDIR

OUTDIR=~/Programowanie/bazy
DBNAME="${2:-bpp}"

TIMESTAMP=`date +%Y-%m-%d_%H:%M`
FILENAME=dump-$TIMESTAMP.pgdump
FN=/tmp/$FILENAME
SAVE_AS="$OUTDIR/$1_$FILENAME"

echo "Uruchamiam SSH celem utworzenia dump bazy danych"
ssh $1 -- "mkdir $FN && pg_dump -j 4 -v -Fd $DBNAME --file=$FN"

echo "Kopiuje dump bazy danych na lokalny komputer"
scp -r $1:$FN $FN

echo "Usuwam dump bazy danych ze zdalnego serwera"
ssh $1 -- rm -r $FN

echo "Zapisuję jako $SAVE_AS"
mv $FN $SAVE_AS
du -h "$SAVE_AS"

echo "Odtwarzam baze danych na lokalnym serwerze"
BASEDIR=$(dirname "$0")
$BASEDIR/odtworz.sh $SAVE_AS

# rm -r $FN
