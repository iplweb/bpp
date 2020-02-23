BEGIN;


UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'a~00', 'α'), zrodlo_s = REPLACE(zrodlo_s, 'a~00', 'α') WHERE (zrodlo LIKE '%a~00%' or zrodlo_s LIKE '%a~00%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'b~00', 'β'), zrodlo_s = REPLACE(zrodlo_s, 'b~00', 'β') WHERE (zrodlo LIKE '%b~00%' or zrodlo_s LIKE '%b~00%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'g~00', 'γ'), zrodlo_s = REPLACE(zrodlo_s, 'g~00', 'γ') WHERE (zrodlo LIKE '%g~00%' or zrodlo_s LIKE '%g~00%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'd~00', 'δ'), zrodlo_s = REPLACE(zrodlo_s, 'd~00', 'δ') WHERE (zrodlo LIKE '%d~00%' or zrodlo_s LIKE '%d~00%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'k~00', 'κ'), zrodlo_s = REPLACE(zrodlo_s, 'k~00', 'κ') WHERE (zrodlo LIKE '%k~00%' or zrodlo_s LIKE '%k~00%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'D~00', 'Δ'), zrodlo_s = REPLACE(zrodlo_s, 'D~00', 'Δ') WHERE (zrodlo LIKE '%D~00%' or zrodlo_s LIKE '%D~00%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'w~00', 'ω'), zrodlo_s = REPLACE(zrodlo_s, 'w~00', 'ω') WHERE (zrodlo LIKE '%w~00%' or zrodlo_s LIKE '%w~00%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'W~00', 'Ω'), zrodlo_s = REPLACE(zrodlo_s, 'W~00', 'Ω') WHERE (zrodlo LIKE '%W~00%' or zrodlo_s LIKE '%W~00%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'r~00', 'ρ'), zrodlo_s = REPLACE(zrodlo_s, 'r~00', 'ρ') WHERE (zrodlo LIKE '%r~00%' or zrodlo_s LIKE '%r~00%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'm~00', 'μ'), zrodlo_s = REPLACE(zrodlo_s, 'm~00', 'μ') WHERE (zrodlo LIKE '%m~00%' or zrodlo_s LIKE '%m~00%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'e~00', 'ε'), zrodlo_s = REPLACE(zrodlo_s, 'e~00', 'ε') WHERE (zrodlo LIKE '%e~00%' or zrodlo_s LIKE '%e~00%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'z~00', 'ζ'), zrodlo_s = REPLACE(zrodlo_s, 'z~00', 'ζ') WHERE (zrodlo LIKE '%z~00%' or zrodlo_s LIKE '%z~00%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'p~00', 'π'), zrodlo_s = REPLACE(zrodlo_s, 'p~00', 'π') WHERE (zrodlo LIKE '%p~00%' or zrodlo_s LIKE '%p~00%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'j~00', 'θ'), zrodlo_s = REPLACE(zrodlo_s, 'j~00', 'θ') WHERE (zrodlo LIKE '%j~00%' or zrodlo_s LIKE '%j~00%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'l~00', 'λ'), zrodlo_s = REPLACE(zrodlo_s, 'l~00', 'λ') WHERE (zrodlo LIKE '%l~00%' or zrodlo_s LIKE '%l~00%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'l~~00', 'λ'), zrodlo_s = REPLACE(zrodlo_s, 'l~~00', 'λ') WHERE (zrodlo LIKE '%l~~00%' or zrodlo_s LIKE '%l~~00%');


UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'e~51', 'ë'), zrodlo_s = REPLACE(zrodlo_s, 'e~51', 'ë') WHERE (zrodlo_s LIKE '%e~51%' OR zrodlo LIKE  '%e~51%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'o~51', 'ö'), zrodlo_s = REPLACE(zrodlo_s, 'o~51', 'ö') WHERE (zrodlo_s LIKE '%o~51%' OR zrodlo LIKE  '%o~51%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'u~51', 'ü'), zrodlo_s = REPLACE(zrodlo_s, 'u~51', 'ü') WHERE (zrodlo_s LIKE '%u~51%' OR zrodlo LIKE  '%u~51%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'c~11', 'ç'), zrodlo_s = REPLACE(zrodlo_s, 'c~11', 'ç') WHERE (zrodlo_s LIKE '%c~11%' OR zrodlo LIKE  '%c~11%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'y~11', 'ý'), zrodlo_s = REPLACE(zrodlo_s, 'y~11', 'ý') WHERE (zrodlo_s LIKE '%y~11%' OR zrodlo LIKE  '%y~11%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'r~11', 'ř'), zrodlo_s = REPLACE(zrodlo_s, 'r~11', 'ř') WHERE (zrodlo_s LIKE '%r~11%' OR zrodlo LIKE  '%r~11%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'E~20', 'É'), zrodlo_s = REPLACE(zrodlo_s, 'E~20', 'É') WHERE (zrodlo_s LIKE '%E~20%' OR zrodlo LIKE  '%E~20%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'C~20', 'Č'), zrodlo_s = REPLACE(zrodlo_s, 'C~20', 'Č') WHERE (zrodlo_s LIKE '%C~20%' OR zrodlo LIKE  '%C~20%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'a~51', 'ä'), zrodlo_s = REPLACE(zrodlo_s, 'a~51', 'ä') WHERE (zrodlo_s LIKE '%a~51%' OR zrodlo LIKE  '%a~51%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'u~41', 'ü'), zrodlo_s = REPLACE(zrodlo_s, 'u~41', 'ü') WHERE (zrodlo LIKE '%u~41%' OR zrodlo_s LIKE '%u~41%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'Sjo~gren', 'Sjögren'), zrodlo_s = REPLACE(zrodlo_s, 'Sjo~gren', 'Sjögren') WHERE (zrodlo LIKE '%Sjo~gren%' OR zrodlo_s LIKE '%Sjo~gren%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'e~21', 'é'), zrodlo_s = REPLACE(zrodlo_s, 'e~21', 'é') WHERE (zrodlo LIKE '%e~21%' OR zrodlo_s LIKE '%e~21%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'n~21', 'ň'), zrodlo_s = REPLACE(zrodlo_s, 'n~21', 'ň') WHERE (zrodlo LIKE '%n~21%' OR zrodlo_s LIKE '%n~21%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'u~21', 'ú'), zrodlo_s = REPLACE(zrodlo_s, 'u~21', 'ú') WHERE (zrodlo LIKE '%u~21%' OR zrodlo_s LIKE '%u~21%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'z~11', 'ž'), zrodlo_s = REPLACE(zrodlo_s, 'z~11', 'ž') WHERE (zrodlo LIKE '%z~11%' OR zrodlo_s LIKE '%z~11%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'o~81', 'ó'), zrodlo_s = REPLACE(zrodlo_s, 'o~81', 'ó') WHERE (zrodlo LIKE '%o~81%' OR zrodlo_s LIKE '%o~81%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'a~81', 'ã'), zrodlo_s = REPLACE(zrodlo_s, 'a~81', 'ã') WHERE (zrodlo LIKE '%a~81%' OR zrodlo_s LIKE '%a~81%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'c~21', 'č'), zrodlo_s = REPLACE(zrodlo_s, 'c~21', 'č') WHERE (zrodlo LIKE '%c~21%' OR zrodlo_s LIKE '%c~21%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'e~31', 'è'), zrodlo_s = REPLACE(zrodlo_s, 'e~31', 'è') WHERE (zrodlo LIKE '%e~31%' OR zrodlo_s LIKE '%e~31%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 's~31', 'š'), zrodlo_s = REPLACE(zrodlo_s, 's~31', 'š') WHERE (zrodlo LIKE '%s~31%' OR zrodlo_s LIKE '%s~31%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'a~31', 'â'), zrodlo_s = REPLACE(zrodlo_s, 'a~31', 'â') WHERE (zrodlo LIKE '%a~31%' OR zrodlo_s LIKE '%a~31%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'o~31', 'ô'), zrodlo_s = REPLACE(zrodlo_s, 'o~31', 'ô') WHERE (zrodlo LIKE '%o~31%' OR zrodlo_s LIKE '%o~31%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'a~21', 'á'), zrodlo_s = REPLACE(zrodlo_s, 'a~21', 'á') WHERE (zrodlo LIKE '%a~21%' OR zrodlo_s LIKE '%a~21%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'a~71', 'à'), zrodlo_s = REPLACE(zrodlo_s, 'a~71', 'à') WHERE (zrodlo LIKE '%a~71%' OR zrodlo_s LIKE '%a~71%');


UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'i~21', 'í'), zrodlo_s = REPLACE(zrodlo_s, 'i~21', 'í') WHERE (zrodlo LIKE '%i~21%' OR zrodlo_s LIKE '%i~21%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'e~41', 'ě'), zrodlo_s = REPLACE(zrodlo_s, 'e~41', 'ě') WHERE (zrodlo LIKE '%e~41%' OR zrodlo_s LIKE '%e~41%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'i~41', 'ï'), zrodlo_s = REPLACE(zrodlo_s, 'i~41', 'ï') WHERE (zrodlo LIKE '%i~41%' OR zrodlo_s LIKE '%i~41%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'o~41', 'ö'), zrodlo_s = REPLACE(zrodlo_s, 'o~41', 'ö') WHERE (zrodlo LIKE '%o~41%' OR zrodlo_s LIKE '%o~41%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'i~61', 'ì'), zrodlo_s = REPLACE(zrodlo_s, 'i~61', 'ì') WHERE (zrodlo LIKE '%i~61%' OR zrodlo_s LIKE '%i~61%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'o~21', 'ö'), zrodlo_s = REPLACE(zrodlo_s, 'o~21', 'ö') WHERE (zrodlo LIKE '%o~21%' OR zrodlo_s LIKE '%o~21%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'a~91', 'ă'), zrodlo_s = REPLACE(zrodlo_s, 'a~91', 'ă') WHERE (zrodlo LIKE '%a~91%' OR zrodlo_s LIKE '%a~91%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'a~61', 'ā'), zrodlo_s = REPLACE(zrodlo_s, 'a~61', 'ā') WHERE (zrodlo LIKE '%a~61%' OR zrodlo_s LIKE '%a~61%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'u~61', 'ū'), zrodlo_s = REPLACE(zrodlo_s, 'u~61', 'ū') WHERE (zrodlo LIKE '%u~61%' OR zrodlo_s LIKE '%u~61%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'i~31', 'î'), zrodlo_s = REPLACE(zrodlo_s, 'i~31', 'î') WHERE (zrodlo LIKE '%i~31%' OR zrodlo_s LIKE '%i~31%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'u~31', 'û'), zrodlo_s = REPLACE(zrodlo_s, 'u~31', 'û') WHERE (zrodlo LIKE '%u~31%' OR zrodlo_s LIKE '%u~31%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 's~41', 'ŝ'), zrodlo_s = REPLACE(zrodlo_s, 's~41', 'ŝ') WHERE (zrodlo LIKE '%s~41%' OR zrodlo_s LIKE '%s~41%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'R~10', 'Ř'), zrodlo_s = REPLACE(zrodlo_s, 'R~10', 'Ř') WHERE (zrodlo LIKE '%R~10%' OR zrodlo_s LIKE '%R~10%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'Z~10', 'Ž'), zrodlo_s = REPLACE(zrodlo_s, 'Z~10', 'Ž') WHERE (zrodlo LIKE '%Z~10%' OR zrodlo_s LIKE '%Z~10%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'S~30', 'Š'), zrodlo_s = REPLACE(zrodlo_s, 'S~30', 'Š') WHERE (zrodlo LIKE '%S~30%' OR zrodlo_s LIKE '%S~30%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'A~50', 'Ä'), zrodlo_s = REPLACE(zrodlo_s, 'A~50', 'Ä') WHERE (zrodlo LIKE '%A~50%' OR zrodlo_s LIKE '%A~50%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'O~50', 'Ö'), zrodlo_s = REPLACE(zrodlo_s, 'O~50', 'Ö') WHERE (zrodlo LIKE '%O~50%' OR zrodlo_s LIKE '%O~50%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'O~70', 'Ò'), zrodlo_s = REPLACE(zrodlo_s, 'O~70', 'Ò') WHERE (zrodlo LIKE '%O~70%' OR zrodlo_s LIKE '%O~70%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'U~40', 'Ü'), zrodlo_s = REPLACE(zrodlo_s, 'U~40', 'Ü') WHERE (zrodlo LIKE '%U~40%' OR zrodlo_s LIKE '%U~40%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'u~91', 'ů'), zrodlo_s = REPLACE(zrodlo_s, 'u~91', 'ů') WHERE (zrodlo LIKE '%u~91%' OR zrodlo_s LIKE '%u~91%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 's~21', 'ş'), zrodlo_s = REPLACE(zrodlo_s, 's~21', 'ş') WHERE (zrodlo LIKE '%s~21%' OR zrodlo_s LIKE '%s~21%');


UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'U~30', 'Û'), zrodlo_s = REPLACE(zrodlo_s, 'U~30', 'Û') WHERE (zrodlo LIKE '%U~30%' OR zrodlo_s LIKE '%U~30%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'S~20', 'Ş'), zrodlo_s = REPLACE(zrodlo_s, 'S~20', 'Ş') WHERE (zrodlo LIKE '%S~20%' OR zrodlo_s LIKE '%S~20%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 't~41', 'ť'), zrodlo_s = REPLACE(zrodlo_s, 't~41', 'ť') WHERE (zrodlo LIKE '%t~41%' OR zrodlo_s LIKE '%t~41%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'l~11', 'ľ'), zrodlo_s = REPLACE(zrodlo_s, 'l~11', 'ľ') WHERE (zrodlo LIKE '%l~11%' OR zrodlo_s LIKE '%l~11%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'E~30', 'È'), zrodlo_s = REPLACE(zrodlo_s, 'E~30', 'È') WHERE (zrodlo LIKE '%E~30%' OR zrodlo_s LIKE '%E~30%');
UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'U~20', 'Ú'), zrodlo_s = REPLACE(zrodlo_s, 'U~20', 'Ú') WHERE (zrodlo LIKE '%U~20%' OR zrodlo_s LIKE '%U~20%');

UPDATE import_dbf_bib SET zrodlo = REPLACE(zrodlo, 'I~60', 'Ì'), zrodlo_s = REPLACE(zrodlo_s, 'I~60', 'Ì') WHERE (zrodlo LIKE '%I~60%' OR zrodlo_s LIKE '%I~60%');

select zrodlo from import_dbf_bib where zrodlo like '%~%';

COMMIT;
