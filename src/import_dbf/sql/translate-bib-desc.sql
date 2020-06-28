BEGIN;

update import_dbf_bib_desc set value = CAST(replace(value::text, 'u~41', 'ü') AS json) where value::text like '%u~41%';
update import_dbf_bib_desc set value = CAST(replace(value::text, 'e~41', 'ě') AS json) where value::text like '%e~41%';
update import_dbf_bib_desc set value = CAST(replace(value::text, 'a~51', 'ä') AS json) where value::text like '%a~51%';
update import_dbf_bib_desc set value = CAST(replace(value::text, 'a~51', 'ä') AS json) where value::text like '%a~51%';
update import_dbf_bib_desc set value = CAST(replace(value::text, 'i~41', 'ï') AS json) where value::text like '%i~41%';

update import_dbf_bib_desc set value = CAST(replace(value::text, 'I~60', 'Ì') AS json) where value::text like '%I~60%';


select * from import_dbf_bib_desc where value::text like '%~%' and value::text not like '%http%';

COMMIT;
