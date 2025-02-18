#!/bin/zsh

# Pobiera token PBN ze zdalnej bazy i ustawia go dla wszystkich użytkowników
# w bazie lokalnej. Używane do testów.

export TOKEN=`ssh $1 -- "echo SELECT pbn_token FROM bpp_bppuser WHERE username = \'$2\' | psql --csv bpp | tail -1"`

echo "UPDATE bpp_bppuser SET pbn_token = '${TOKEN}', pbn_token_updated = NOW()" | psql bpp > /dev/null

echo $TOKEN has been set for all users in local database
