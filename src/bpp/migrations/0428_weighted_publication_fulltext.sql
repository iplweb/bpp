BEGIN;

CREATE OR REPLACE FUNCTION bpp_publication_weighted_search_vector(
    p_tytul_oryginalny TEXT,
    p_tytul TEXT,
    p_autorzy TEXT,
    p_rok INTEGER,
    p_doi TEXT,
    p_opis_bibliograficzny TEXT
) RETURNS tsvector AS $$
    SELECT
        setweight(
            to_tsvector(
                'bpp_nazwy_wlasne',
                strip_tags(COALESCE(p_tytul_oryginalny, ''))
            ),
            'A'
        ) ||
        setweight(
            to_tsvector(
                'bpp_nazwy_wlasne',
                strip_tags(COALESCE(p_tytul, ''))
            ),
            'A'
        ) ||
        setweight(
            to_tsvector(
                'bpp_nazwy_wlasne',
                strip_tags(COALESCE(p_autorzy, ''))
            ),
            'B'
        ) ||
        setweight(
            to_tsvector(
                'bpp_nazwy_wlasne',
                COALESCE(p_doi, '') || ' ' ||
                regexp_replace(COALESCE(p_doi, ''), '[^[:alnum:]]+', '', 'g')
            ),
            'B'
        ) ||
        setweight(
            to_tsvector('bpp_nazwy_wlasne', COALESCE(p_rok::TEXT, '')),
            'C'
        ) ||
        setweight(
            to_tsvector(
                'bpp_nazwy_wlasne',
                strip_tags(COALESCE(p_opis_bibliograficzny, ''))
            ),
            'D'
        );
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION bpp_publication_author_search_text(
    p_zapisani_autorzy TEXT,
    p_autorzy TEXT[]
) RETURNS TEXT AS $$
    SELECT concat_ws(' ', p_zapisani_autorzy, array_to_string(p_autorzy, ' '));
$$ LANGUAGE SQL;

CREATE OR REPLACE FUNCTION ts_post_bpp_wydawnictwo_ciagle_search()
RETURNS trigger AS $$
BEGIN
    NEW.search_index := bpp_publication_weighted_search_vector(
        NEW.tytul_oryginalny,
        NEW.tytul,
        bpp_publication_author_search_text(
            NEW.opis_bibliograficzny_zapisani_autorzy_cache,
            NEW.opis_bibliograficzny_autorzy_cache
        ),
        NEW.rok,
        NEW.doi,
        NEW.opis_bibliograficzny_cache
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ts_post_bpp_wydawnictwo_zwarte_search()
RETURNS trigger AS $$
BEGIN
    NEW.search_index := bpp_publication_weighted_search_vector(
        NEW.tytul_oryginalny,
        NEW.tytul,
        bpp_publication_author_search_text(
            NEW.opis_bibliograficzny_zapisani_autorzy_cache,
            NEW.opis_bibliograficzny_autorzy_cache
        ),
        NEW.rok,
        NEW.doi,
        NEW.opis_bibliograficzny_cache
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ts_post_bpp_praca_doktorska_search()
RETURNS trigger AS $$
BEGIN
    NEW.search_index := bpp_publication_weighted_search_vector(
        NEW.tytul_oryginalny,
        NEW.tytul,
        bpp_publication_author_search_text(
            NEW.opis_bibliograficzny_zapisani_autorzy_cache,
            NEW.opis_bibliograficzny_autorzy_cache
        ),
        NEW.rok,
        NEW.doi,
        NEW.opis_bibliograficzny_cache
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ts_post_bpp_praca_habilitacyjna_search()
RETURNS trigger AS $$
BEGIN
    NEW.search_index := bpp_publication_weighted_search_vector(
        NEW.tytul_oryginalny,
        NEW.tytul,
        bpp_publication_author_search_text(
            NEW.opis_bibliograficzny_zapisani_autorzy_cache,
            NEW.opis_bibliograficzny_autorzy_cache
        ),
        NEW.rok,
        NEW.doi,
        NEW.opis_bibliograficzny_cache
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ts_post_bpp_patent_search()
RETURNS trigger AS $$
BEGIN
    NEW.search_index := bpp_publication_weighted_search_vector(
        NEW.tytul_oryginalny,
        NULL,
        bpp_publication_author_search_text(
            NEW.opis_bibliograficzny_zapisani_autorzy_cache,
            NEW.opis_bibliograficzny_autorzy_cache
        ),
        NEW.rok,
        NULL,
        NEW.opis_bibliograficzny_cache
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

UPDATE bpp_wydawnictwo_ciagle SET id = id;
UPDATE bpp_wydawnictwo_zwarte SET id = id;
UPDATE bpp_praca_doktorska SET id = id;
UPDATE bpp_praca_habilitacyjna SET id = id;
UPDATE bpp_patent SET id = id;

COMMIT;
