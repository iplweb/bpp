BEGIN;

-- VIEW: bpp_rekord
-- VIEW: bpp_autorzy

DROP TABLE IF EXISTS bpp_rekord_mat CASCADE;
CREATE TABLE bpp_rekord_mat AS SELECT * FROM bpp_rekord;


CREATE UNIQUE INDEX bpp_rekord_mat_fake_id_idx ON bpp_rekord_mat(fake_id);
CREATE UNIQUE INDEX bpp_rekord_mat_original_idx ON bpp_rekord_mat(content_type_id, object_id);

CREATE INDEX bpp_rekord_mat_tytul_oryginalny_idx ON bpp_rekord_mat(tytul_oryginalny);
CREATE INDEX bpp_rekord_mat_search_index_idx ON bpp_rekord_mat USING GIST(search_index);
CREATE INDEX bpp_rekord_mat_1 ON bpp_rekord_mat(jezyk_id);
CREATE INDEX bpp_rekord_mat_2 ON bpp_rekord_mat(typ_kbn_id);
CREATE INDEX bpp_rekord_mat_3 ON bpp_rekord_mat(charakter_formalny_id);
CREATE INDEX bpp_rekord_mat_4 ON bpp_rekord_mat(zrodlo_id);
CREATE INDEX bpp_rekord_mat_5 ON bpp_rekord_mat(wydawnictwo);
CREATE INDEX bpp_rekord_mat_6 ON bpp_rekord_mat(slowa_kluczowe);
CREATE INDEX bpp_rekord_mat_7 ON bpp_rekord_mat(impact_factor);
CREATE INDEX bpp_rekord_mat_8 ON bpp_rekord_mat(punkty_kbn);
CREATE INDEX bpp_rekord_mat_9 ON bpp_rekord_mat(index_copernicus);
CREATE INDEX bpp_rekord_mat_a ON bpp_rekord_mat(punktacja_wewnetrzna);
CREATE INDEX bpp_rekord_mat_b ON bpp_rekord_mat(kc_impact_factor);
CREATE INDEX bpp_rekord_mat_c ON bpp_rekord_mat(kc_punkty_kbn);
CREATE INDEX bpp_rekord_mat_d ON bpp_rekord_mat(kc_index_copernicus);
CREATE INDEX bpp_rekord_mat_e ON bpp_rekord_mat(uwagi);
CREATE INDEX bpp_rekord_mat_f ON bpp_rekord_mat(adnotacje);
CREATE INDEX bpp_rekord_mat_g ON bpp_rekord_mat(utworzono);
CREATE INDEX bpp_rekord_mat_h ON bpp_rekord_mat(ostatnio_zmieniony);
CREATE INDEX bpp_rekord_mat_i ON bpp_rekord_mat(rok);
CREATE INDEX bpp_rekord_mat_j ON bpp_rekord_mat(afiliowana);
CREATE INDEX bpp_rekord_mat_k ON bpp_rekord_mat(recenzowana);

ALTER TABLE bpp_rekord_mat ADD CONSTRAINT zrodlo_id_fk FOREIGN KEY (zrodlo_id) REFERENCES bpp_zrodlo (id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED ;
ALTER TABLE bpp_rekord_mat ADD CONSTRAINT charakter_formalny_id_fk FOREIGN KEY (charakter_formalny_id) REFERENCES bpp_charakter_formalny (id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED ;
ALTER TABLE bpp_rekord_mat ADD CONSTRAINT jezyk_id_fk FOREIGN KEY (jezyk_id) REFERENCES bpp_jezyk (id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED ;
ALTER TABLE bpp_rekord_mat ADD CONSTRAINT typ_kbn_id_fk FOREIGN KEY (typ_kbn_id) REFERENCES bpp_typ_kbn (id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED ;


DROP TABLE IF EXISTS bpp_autorzy_mat CASCADE;
CREATE TABLE bpp_autorzy_mat AS SELECT * FROM bpp_autorzy;

CREATE UNIQUE INDEX bpp_autorzy_mat_0 ON bpp_autorzy_mat(fake_id);
CREATE UNIQUE INDEX bpp_autorzy_mat_1 ON bpp_autorzy_mat(content_type_id, object_id, autor_id, typ_odpowiedzialnosci_id, kolejnosc);
CREATE UNIQUE INDEX bpp_autorzy_mat_11 ON bpp_autorzy_mat(content_type_id, object_id, autor_id, kolejnosc);

CREATE INDEX bpp_autorzy_mat_2 ON bpp_autorzy_mat(autor_id);
CREATE INDEX bpp_autorzy_mat_3 ON bpp_autorzy_mat(jednostka_id);
CREATE INDEX bpp_autorzy_mat_4 ON bpp_autorzy_mat(autor_id, jednostka_id);
CREATE INDEX bpp_autorzy_mat_5 ON bpp_autorzy_mat(autor_id, typ_odpowiedzialnosci_id);

ALTER TABLE bpp_autorzy_mat ADD CONSTRAINT original_id_fk FOREIGN KEY (content_type_id, object_id) REFERENCES bpp_rekord_mat(content_type_id, object_id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED ;
ALTER TABLE bpp_autorzy_mat ADD CONSTRAINT jednostka_id_fk FOREIGN KEY (jednostka_id) REFERENCES bpp_jednostka(id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED ;
ALTER TABLE bpp_autorzy_mat ADD CONSTRAINT autor_id_fk FOREIGN KEY (autor_id) REFERENCES bpp_autor(id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED ;
ALTER TABLE bpp_autorzy_mat ADD CONSTRAINT typ_odpowiedzialnosci_id_fk FOREIGN KEY (typ_odpowiedzialnosci_id) REFERENCES bpp_typ_odpowiedzialnosci(id) ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED ;  -- fore ON DELETE CASCADE ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED ;


COMMIT;