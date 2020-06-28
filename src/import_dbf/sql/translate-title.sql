BEGIN;


UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'a~00', 'α'), title = REPLACE(title, 'a~00', 'α') WHERE (tytul_or LIKE '%a~00%' or title LIKE '%a~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'b~00', 'β'), title = REPLACE(title, 'b~00', 'β') WHERE (tytul_or LIKE '%b~00%' or title LIKE '%b~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'g~00', 'γ'), title = REPLACE(title, 'g~00', 'γ') WHERE (tytul_or LIKE '%g~00%' or title LIKE '%g~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'd~00', 'δ'), title = REPLACE(title, 'd~00', 'δ') WHERE (tytul_or LIKE '%d~00%' or title LIKE '%d~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'k~00', 'κ'), title = REPLACE(title, 'k~00', 'κ') WHERE (tytul_or LIKE '%k~00%' or title LIKE '%k~00%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'D~00', 'Δ'), title = REPLACE(title, 'D~00', 'Δ') WHERE (tytul_or LIKE '%D~00%' or title LIKE '%D~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'w~00', 'ω'), title = REPLACE(title, 'w~00', 'ω') WHERE (tytul_or LIKE '%w~00%' or title LIKE '%w~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'W~00', 'Ω'), title = REPLACE(title, 'W~00', 'Ω') WHERE (tytul_or LIKE '%W~00%' or title LIKE '%W~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'r~00', 'ρ'), title = REPLACE(title, 'r~00', 'ρ') WHERE (tytul_or LIKE '%r~00%' or title LIKE '%r~00%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'm~00', 'μ'), title = REPLACE(title, 'm~00', 'μ') WHERE (tytul_or LIKE '%m~00%' or title LIKE '%m~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'e~00', 'ε'), title = REPLACE(title, 'e~00', 'ε') WHERE (tytul_or LIKE '%e~00%' or title LIKE '%e~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'z~00', 'ζ'), title = REPLACE(title, 'z~00', 'ζ') WHERE (tytul_or LIKE '%z~00%' or title LIKE '%z~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'p~00', 'π'), title = REPLACE(title, 'p~00', 'π') WHERE (tytul_or LIKE '%p~00%' or title LIKE '%p~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'j~00', 'θ'), title = REPLACE(title, 'j~00', 'θ') WHERE (tytul_or LIKE '%j~00%' or title LIKE '%j~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'l~00', 'λ'), title = REPLACE(title, 'l~00', 'λ') WHERE (tytul_or LIKE '%l~00%' or title LIKE '%l~00%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'l~~00', 'λ'), title = REPLACE(title, 'l~~00', 'λ') WHERE (tytul_or LIKE '%l~~00%' or title LIKE '%l~~00%');


UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'e~51', 'ë'), title = REPLACE(title, 'e~51', 'ë') WHERE (title LIKE '%e~51%' OR tytul_or LIKE  '%e~51%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'e~81', 'ê'), title = REPLACE(title, 'e~81', 'ê') WHERE (title LIKE '%e~81%' OR tytul_or LIKE  '%e~81%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'o~51', 'ö'), title = REPLACE(title, 'o~51', 'ö') WHERE (title LIKE '%o~51%' OR tytul_or LIKE  '%o~51%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'u~51', 'ü'), title = REPLACE(title, 'u~51', 'ü') WHERE (title LIKE '%u~51%' OR tytul_or LIKE  '%u~51%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'c~11', 'ç'), title = REPLACE(title, 'c~11', 'ç') WHERE (title LIKE '%c~11%' OR tytul_or LIKE  '%c~11%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'y~11', 'ý'), title = REPLACE(title, 'y~11', 'ý') WHERE (title LIKE '%y~11%' OR tytul_or LIKE  '%y~11%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'r~11', 'ř'), title = REPLACE(title, 'r~11', 'ř') WHERE (title LIKE '%r~11%' OR tytul_or LIKE  '%r~11%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'E~20', 'É'), title = REPLACE(title, 'E~20', 'É') WHERE (title LIKE '%E~20%' OR tytul_or LIKE  '%E~20%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'C~20', 'Č'), title = REPLACE(title, 'C~20', 'Č') WHERE (title LIKE '%C~20%' OR tytul_or LIKE  '%C~20%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'a~51', 'ä'), title = REPLACE(title, 'a~51', 'ä') WHERE (title LIKE '%a~51%' OR tytul_or LIKE  '%a~51%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'u~41', 'ü'), title = REPLACE(title, 'u~41', 'ü') WHERE (tytul_or LIKE '%u~41%' OR title LIKE '%u~41%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'Sjo~gren', 'Sjögren'), title = REPLACE(title, 'Sjo~gren', 'Sjögren') WHERE (tytul_or LIKE '%Sjo~gren%' OR title LIKE '%Sjo~gren%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'e~21', 'é'), title = REPLACE(title, 'e~21', 'é') WHERE (tytul_or LIKE '%e~21%' OR title LIKE '%e~21%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'e~21', 'é'), title = REPLACE(title, 'e~21', 'é') WHERE (tytul_or LIKE '%e~21%' OR title LIKE '%e~21%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'n~21', 'ň'), title = REPLACE(title, 'n~21', 'ň') WHERE (tytul_or LIKE '%n~21%' OR title LIKE '%n~21%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'u~21', 'ú'), title = REPLACE(title, 'u~21', 'ú') WHERE (tytul_or LIKE '%u~21%' OR title LIKE '%u~21%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'z~11', 'ž'), title = REPLACE(title, 'z~11', 'ž') WHERE (tytul_or LIKE '%z~11%' OR title LIKE '%z~11%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'o~81', 'ó'), title = REPLACE(title, 'o~81', 'ó') WHERE (tytul_or LIKE '%o~81%' OR title LIKE '%o~81%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'a~81', 'ã'), title = REPLACE(title, 'a~81', 'ã') WHERE (tytul_or LIKE '%a~81%' OR title LIKE '%a~81%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'c~21', 'č'), title = REPLACE(title, 'c~21', 'č') WHERE (tytul_or LIKE '%c~21%' OR title LIKE '%c~21%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'e~31', 'è'), title = REPLACE(title, 'e~31', 'è') WHERE (tytul_or LIKE '%e~31%' OR title LIKE '%e~31%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 's~31', 'š'), title = REPLACE(title, 's~31', 'š') WHERE (tytul_or LIKE '%s~31%' OR title LIKE '%s~31%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'a~31', 'â'), title = REPLACE(title, 'a~31', 'â') WHERE (tytul_or LIKE '%a~31%' OR title LIKE '%a~31%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'o~31', 'ô'), title = REPLACE(title, 'o~31', 'ô') WHERE (tytul_or LIKE '%o~31%' OR title LIKE '%o~31%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'a~21', 'á'), title = REPLACE(title, 'a~21', 'á') WHERE (tytul_or LIKE '%a~21%' OR title LIKE '%a~21%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'a~71', 'à'), title = REPLACE(title, 'a~71', 'à') WHERE (tytul_or LIKE '%a~71%' OR title LIKE '%a~71%');


UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'i~21', 'í'), title = REPLACE(title, 'i~21', 'í') WHERE (tytul_or LIKE '%i~21%' OR title LIKE '%i~21%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'e~41', 'ě'), title = REPLACE(title, 'e~41', 'ě') WHERE (tytul_or LIKE '%e~41%' OR title LIKE '%e~41%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'i~41', 'ï'), title = REPLACE(title, 'i~41', 'ï') WHERE (tytul_or LIKE '%i~41%' OR title LIKE '%i~41%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'o~41', 'ö'), title = REPLACE(title, 'o~41', 'ö') WHERE (tytul_or LIKE '%o~41%' OR title LIKE '%o~41%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'i~61', 'ì'), title = REPLACE(title, 'i~61', 'ì') WHERE (tytul_or LIKE '%i~61%' OR title LIKE '%i~61%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'o~21', 'ö'), title = REPLACE(title, 'o~21', 'ö') WHERE (tytul_or LIKE '%o~21%' OR title LIKE '%o~21%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'a~91', 'ă'), title = REPLACE(title, 'a~91', 'ă') WHERE (tytul_or LIKE '%a~91%' OR title LIKE '%a~91%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'a~61', 'ā'), title = REPLACE(title, 'a~61', 'ā') WHERE (tytul_or LIKE '%a~61%' OR title LIKE '%a~61%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'u~61', 'ū'), title = REPLACE(title, 'u~61', 'ū') WHERE (tytul_or LIKE '%u~61%' OR title LIKE '%u~61%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'i~31', 'î'), title = REPLACE(title, 'i~31', 'î') WHERE (tytul_or LIKE '%i~31%' OR title LIKE '%i~31%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'u~31', 'û'), title = REPLACE(title, 'u~31', 'û') WHERE (tytul_or LIKE '%u~31%' OR title LIKE '%u~31%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 's~41', 'ŝ'), title = REPLACE(title, 's~41', 'ŝ') WHERE (tytul_or LIKE '%s~41%' OR title LIKE '%s~41%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'R~10', 'Ř'), title = REPLACE(title, 'R~10', 'Ř') WHERE (tytul_or LIKE '%R~10%' OR title LIKE '%R~10%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'Z~10', 'Ž'), title = REPLACE(title, 'Z~10', 'Ž') WHERE (tytul_or LIKE '%Z~10%' OR title LIKE '%Z~10%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'S~30', 'Š'), title = REPLACE(title, 'S~30', 'Š') WHERE (tytul_or LIKE '%S~30%' OR title LIKE '%S~30%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'A~50', 'Ä'), title = REPLACE(title, 'A~50', 'Ä') WHERE (tytul_or LIKE '%A~50%' OR title LIKE '%A~50%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'O~50', 'Ö'), title = REPLACE(title, 'O~50', 'Ö') WHERE (tytul_or LIKE '%O~50%' OR title LIKE '%O~50%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'O~70', 'Ò'), title = REPLACE(title, 'O~70', 'Ò') WHERE (tytul_or LIKE '%O~70%' OR title LIKE '%O~70%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'U~40', 'Ü'), title = REPLACE(title, 'U~40', 'Ü') WHERE (tytul_or LIKE '%U~40%' OR title LIKE '%U~40%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'u~91', 'ů'), title = REPLACE(title, 'u~91', 'ů') WHERE (tytul_or LIKE '%u~91%' OR title LIKE '%u~91%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 's~21', 'ş'), title = REPLACE(title, 's~21', 'ş') WHERE (tytul_or LIKE '%s~21%' OR title LIKE '%s~21%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'S~20', 'Ş'), title = REPLACE(title, 'S~20', 'Ş') WHERE (tytul_or LIKE '%S~20%' OR title LIKE '%S~20%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'I~60', 'Ì'), title = REPLACE(title, 'I~60', 'Ì') WHERE (tytul_or LIKE '%I~60%' OR title LIKE '%I~60%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 't~41', 'ť'), title = REPLACE(title, 't~41', 'ť') WHERE (tytul_or LIKE '%t~41%' OR title LIKE '%t~41%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'U~30', 'Û'), title = REPLACE(title, 'U~30', 'Û') WHERE (tytul_or LIKE '%U~30%' OR title LIKE '%U~30%');
UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'U~20', 'Ú'), title = REPLACE(title, 'U~20', 'Ú') WHERE (tytul_or LIKE '%U~20%' OR title LIKE '%U~20%');

UPDATE import_dbf_bib SET tytul_or = REPLACE(tytul_or, 'l~11', 'ľ'), title = REPLACE(title, 'l~11', 'ľ') WHERE (tytul_or LIKE '%l~11%' OR title LIKE '%l~11%');



select title from import_dbf_bib where title like '%~%';
select tytul_or from import_dbf_bib where tytul_or like '%~%';


COMMIT;
