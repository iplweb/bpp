#!/bin/sh

perform() {
    psql --csv bpp -c "$2" | python bin/csv2xlsx.py > $1
}

# Czasopisma z numerem MNISW ID zaczynającym się od '100'
perform czasopisma_od_100.xlsx "SELECT * FROM (SELECT \"mongoId\", versions#>'{0}'->'object'->>'title' AS tytul, versions#>'{0}'->'object'->'mniswId' AS mniswId FROM pbn_api_journal WHERE versions @> '[{\"current\": true}]') X WHERE mniswId::text LIKE '100%'"

perform autorzy_z_orcid_nieistniejacym_w_pbn.xlsx "SELECT id, imiona, nazwisko, orcid FROM bpp_autor WHERE pbn_uid_id IS NULL AND orcid_w_pbn IS false AND orcid IS NOT NULL ORDER BY nazwisko, imiona"

perform zrodla_z_issn_lub_eissn_bez_odpowiednika_w_pbn.xlsx "SELECT id, nazwa, issn, e_issn FROM bpp_zrodlo WHERE pbn_uid_id IS NULL AND (issn IS NOT NULL OR e_issn IS NOT NULL)"

perform zrodla_zmatchowane_ale_bez_mnisw_id.xlsx "select id, nazwa from bpp_zrodlo, pbn_api_journal where pbn_api_journal.\"mniswId\" is NULL and bpp_zrodlo.pbn_uid_id = pbn_api_journal.\"mongoId\" order by nazwa;"

perform zrodla_zmatchowane_z_mnisw_id.xlsx "select id, nazwa, pbn_uid_id, pbn_api_journal.\"mniswId\" from bpp_zrodlo, pbn_api_journal where pbn_api_journal.\"mniswId\" IS NOT NULL and bpp_zrodlo.pbn_uid_id = pbn_api_journal.\"mongoId\" order by nazwa;"

perform jednostki_bez_odpowiednika_w_pbn.xlsx "SELECT id, nazwa FROM bpp_jednostka WHERE pbn_uid_id IS NULL"

perform wydawcy_bez_odpowiednika_w_pbn.xlsx "SELECT id, nazwa FROM bpp_wydawca  WHERE pbn_uid_id IS NULL"

perform zdublowane_zrodla_po_stronie_bpp.xlsx "select pbn_uid_id, array_agg(id) as numery_id, array_agg(nazwa) as nazwy from bpp_zrodlo  where pbn_uid_id is not null group by pbn_uid_id having count(pbn_uid_id) > 1;"

perform zdublowane_public_www_po_stronie_bpp.xlsx "select public_www, array_agg(id[2]) as numery_id  from bpp_rekord  where public_www is not null and public_www != '' group by public_www having count(public_www) > 1 ;"

perform zdublowane_www_po_stronie_bpp.xlsx "select www, array_agg(id[2]) as numery_id  from bpp_rekord  where www is not null and www != '' group by www having count(www) > 1 ;"

perform zdublowane_pbn_uid_id_publikacji.xlsx "select pbn_uid_id, array_agg(id[2]) as numery_id  from bpp_rekord  where pbn_uid_id is not null group by pbn_uid_id having count(pbn_uid_id) > 1;"

perform zdublowani_pbn_uid_id_autorzy.xlsx "select pbn_uid_id, array_agg(nazwisko || ' ' || imiona) as nazwiska, array_agg(id) as id  from bpp_autor  where pbn_uid_id is not null group by pbn_uid_id having count(pbn_uid_id) > 1 ;"

perform potencjalnie_zle_zmatchowane_prace.xlsx "select bpp_rekord.tytul_oryginalny, pbn_api_publication.title, pbn_api_publication.\"mongoId\" from bpp_rekord, pbn_api_publication where bpp_rekord.pbn_uid_id = pbn_api_publication.\"mongoId\" and similarity(bpp_rekord.tytul_oryginalny, pbn_api_publication.title) < 0.99 order by similarity(bpp_rekord.tytul_oryginalny, pbn_api_publication.title) asc;"


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

# Prace z dyscyplina, bez matchu w PBN, bedace wydawnictwami nadrzednymi
perform prace_z_dyscyplina_bez_matchu_w_pbn_zwarte_nadrzedne.xlsx "SELECT DISTINCT tytul_oryginalny, rok FROM bpp_wydawnictwo_zwarte WHERE id IN (SELECT DISTINCT rekord_id FROM bpp_wydawnictwo_zwarte_autor WHERE dyscyplina_naukowa_id IS NOT NULL) AND pbn_uid_id IS NULL AND id IN (SELECT DISTINCT wydawnictwo_nadrzedne_id FROM bpp_wydawnictwo_zwarte) AND rok >= 2017"

# Prace z dyscyplina, bez matchu w PBN
perform prace_z_dyscyplina_bez_matchu_w_pbn_zwarte.xlsx "SELECT DISTINCT tytul_oryginalny, rok FROM bpp_wydawnictwo_zwarte WHERE id IN (SELECT DISTINCT rekord_id FROM bpp_wydawnictwo_zwarte_autor WHERE dyscyplina_naukowa_id IS NOT NULL) AND pbn_uid_id IS NULL"

perform prace_z_dyscyplina_bez_matchu_w_pbn_ciagle.xlsx "SELECT DISTINCT tytul_oryginalny, rok FROM bpp_wydawnictwo_ciagle WHERE id IN (SELECT DISTINCT rekord_id FROM bpp_wydawnictwo_ciagle_autor WHERE dyscyplina_naukowa_id IS NOT NULL) AND pbn_uid_id IS NULL"

# Prace z oswiadczeniami w PBN bez matchu po stronie BPP
perform prace_z_oswiadczeniami_w_pbnie_bez_matchu_w_bpp.xlsx "SELECT distinct \"publicationId_id\", pbn_api_publication.title FROM pbn_api_oswiadczenieinstytucji, pbn_api_publication WHERE pbn_api_publication.\"mongoId\" = pbn_api_oswiadczenieinstytucji.\"publicationId_id\" and \"publicationId_id\" NOT IN (SELECT DISTINCT pbn_uid_id FROM bpp_rekord WHERE pbn_uid_id is not null);"
