#!/bin/sh

perform() {
    psql --csv bpp -c "$2" | python bin/csv2xlsx.py > $1
}

# Czasopisma z numerem MNISW ID zaczynającym się od '100'
perform czasopisma_od_100.xlsx "SELECT * FROM (SELECT \"mongoId\", versions#>'{0}'->'object'->>'title' AS tytul, versions#>'{0}'->'object'->'mniswId' AS mniswId FROM pbn_api_journal WHERE versions @> '[{\"current\": true}]') X WHERE mniswId::text LIKE '100%'"

perform autorzy_z_orcid_nieistniejacym_w_pbn.xlsx "SELECT id, imiona, nazwisko, orcid FROM bpp_autor WHERE pbn_uid_id IS NULL AND orcid_w_pbn IS false AND orcid IS NOT NULL ORDER BY nazwisko, imiona"

perform zrodla_z_issn_lub_eissn_bez_odpowiednika_w_pbn.xlsx "SELECT id, nazwa, issn, e_issn FROM bpp_zrodlo WHERE pbn_uid_id IS NULL AND (issn IS NOT NULL OR e_issn IS NOT NULL)"

perform zrodla_zmatchowane_ale_bez_mnisw_id.xlsx "select id, nazwa from bpp_zrodlo, pbn_api_journal where pbn_api_journal.\"mniswId\" is NULL and bpp_zrodlo.pbn_uid_id = pbn_api_journal.\"mongoId\" order by nazwa;"

perform jednostki_bez_odpowiednika_w_pbn.xlsx "SELECT id, nazwa FROM bpp_jednostka WHERE pbn_uid_id IS NULL"

perform wydawcy_bez_odpowiednika_w_pbn.xlsx "SELECT id, nazwa FROM bpp_wydawca  WHERE pbn_uid_id IS NULL"

# "nasi" autorzy -- to sa ludzie z dyscypliną
# SELECT DISTINCT autor_id FROM bpp_autor_dyscyaplina

# "nasi" autorzy z api instytucji
# SELECT "mongoId" FROM pbn_api_scientist WHERE from_institution_api IS TRUE

# Wybierz nazwiska, imiona i tytuy
# SELECT "mongoId", versions#>'{0}'->'object'->>'name',versions#>'{0}'->'object'->>'lastName', versions#>'{0}'->'object'->>'qualifications' FROM pbn_api_scientist WHERE versions @> '[{"current": true}]'

# Wybierz aktualne rekordy (current: True)
# select * from pbn_api_scientist where versions @> '[{"current": true}]'

# Wszyscy "nasi" autorzy bez PBN_UID
perform autorzy_z_dyscyplina_bez_odpowiednika_pbn.xlsx "SELECT id, nazwisko, imiona FROM bpp_autor WHERE pbn_uid_id IS NULL AND id IN (SELECT DISTINCT autor_id FROM bpp_autor_dyscyplina);"

# Wszyscy "instytucjonalni" autorzy bez matchu
perform autorzy_z_pbn_bez_odpowiednika_w_bpp.xlsx "SELECT \"mongoId\", versions#>'{0}'->'object'->>'name',versions#>'{0}'->'object'->>'lastName', versions#>'{0}'->'object'->>'qualifications' FROM pbn_api_scientist WHERE versions @> '[{\"current\": true}]' AND from_institution_api IS TRUE AND \"mongoId\" NOT IN (SELECT DISTINCT \"pbn_uid_id\" FROM bpp_autor WHERE pbn_uid_id IS NOT NULL)"
