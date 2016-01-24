BEGIN;


CREATE OR REPLACE FUNCTION public.pg_find_index(tabl text, col text)
 RETURNS SETOF name
 LANGUAGE plpgsql
AS $function$

BEGIN
RETURN QUERY EXECUTE '
select
    i.relname as index_name
from
    pg_class t,
    pg_class i,
    pg_index ix,
    pg_attribute a
where
    t.oid = ix.indrelid
    and i.oid = ix.indexrelid
    and a.attrelid = t.oid
    and a.attnum = ANY(ix.indkey)
    and t.relkind = ''r''
    and t.relname = $1
    and a.attname = $2
' USING tabl, col;
RETURN;
END;
$function$;



CREATE INDEX bpp_praca_doktorska_ts ON bpp_praca_doktorska USING GIST(search_index);
CREATE INDEX bpp_praca_habilitacyjna_ts ON bpp_praca_habilitacyjna USING GIST(search_index);
CREATE INDEX bpp_wydawnictwo_ciagle_ts ON bpp_wydawnictwo_ciagle USING GIST(search_index);
CREATE INDEX bpp_wydawnictwo_zwarte_ts ON bpp_wydawnictwo_zwarte USING GIST(search_index);
CREATE INDEX bpp_patent_ts ON bpp_patent USING GIST(search_index);

CREATE INDEX bpp_autor_ts ON bpp_autor USING gist(search);
CREATE INDEX bpp_jednostka_ts ON bpp_jednostka USING gist(search);
CREATE INDEX bpp_zrodlo_ts ON bpp_zrodlo USING gist(search);




CREATE OR REPLACE FUNCTION pg_find_index(tabl TEXT, col TEXT)
  RETURNS SETOF name
AS $$

BEGIN
RETURN QUERY EXECUTE

'
select
    i.relname as index_name
from
    pg_class t,
    pg_class i,
    pg_index ix,
    pg_attribute a
where
    t.oid = ix.indrelid
    and i.oid = ix.indexrelid
    and a.attrelid = t.oid
    and a.attnum = ANY(ix.indkey)
    and t.relkind = ''r''
    and t.relname = $1
    and a.attname = $2
' USING tabl, col;
RETURN;
END;

$$ LANGUAGE plpgsql;

SELECT pg_find_index('bpp_autor', 'nazwisko');


COMMIT;