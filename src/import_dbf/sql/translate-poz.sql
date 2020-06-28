BEGIN;


UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'a~00', 'α'), kod_opisu = REPLACE(kod_opisu, 'a~00', 'α') WHERE (tresc LIKE '%a~00%' or kod_opisu LIKE '%a~00%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'b~00', 'β'), kod_opisu = REPLACE(kod_opisu, 'b~00', 'β') WHERE (tresc LIKE '%b~00%' or kod_opisu LIKE '%b~00%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'g~00', 'γ'), kod_opisu = REPLACE(kod_opisu, 'g~00', 'γ') WHERE (tresc LIKE '%g~00%' or kod_opisu LIKE '%g~00%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'd~00', 'δ'), kod_opisu = REPLACE(kod_opisu, 'd~00', 'δ') WHERE (tresc LIKE '%d~00%' or kod_opisu LIKE '%d~00%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'k~00', 'κ'), kod_opisu = REPLACE(kod_opisu, 'k~00', 'κ') WHERE (tresc LIKE '%k~00%' or kod_opisu LIKE '%k~00%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'D~00', 'Δ'), kod_opisu = REPLACE(kod_opisu, 'D~00', 'Δ') WHERE (tresc LIKE '%D~00%' or kod_opisu LIKE '%D~00%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'w~00', 'ω'), kod_opisu = REPLACE(kod_opisu, 'w~00', 'ω') WHERE (tresc LIKE '%w~00%' or kod_opisu LIKE '%w~00%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'W~00', 'Ω'), kod_opisu = REPLACE(kod_opisu, 'W~00', 'Ω') WHERE (tresc LIKE '%W~00%' or kod_opisu LIKE '%W~00%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'r~00', 'ρ'), kod_opisu = REPLACE(kod_opisu, 'r~00', 'ρ') WHERE (tresc LIKE '%r~00%' or kod_opisu LIKE '%r~00%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'm~00', 'μ'), kod_opisu = REPLACE(kod_opisu, 'm~00', 'μ') WHERE (tresc LIKE '%m~00%' or kod_opisu LIKE '%m~00%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'e~00', 'ε'), kod_opisu = REPLACE(kod_opisu, 'e~00', 'ε') WHERE (tresc LIKE '%e~00%' or kod_opisu LIKE '%e~00%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'z~00', 'ζ'), kod_opisu = REPLACE(kod_opisu, 'z~00', 'ζ') WHERE (tresc LIKE '%z~00%' or kod_opisu LIKE '%z~00%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'p~00', 'π'), kod_opisu = REPLACE(kod_opisu, 'p~00', 'π') WHERE (tresc LIKE '%p~00%' or kod_opisu LIKE '%p~00%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'j~00', 'θ'), kod_opisu = REPLACE(kod_opisu, 'j~00', 'θ') WHERE (tresc LIKE '%j~00%' or kod_opisu LIKE '%j~00%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'l~00', 'λ'), kod_opisu = REPLACE(kod_opisu, 'l~00', 'λ') WHERE (tresc LIKE '%l~00%' or kod_opisu LIKE '%l~00%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'l~~00', 'λ'), kod_opisu = REPLACE(kod_opisu, 'l~~00', 'λ') WHERE (tresc LIKE '%l~~00%' or kod_opisu LIKE '%l~~00%');


UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'e~51', 'ë'), kod_opisu = REPLACE(kod_opisu, 'e~51', 'ë') WHERE (kod_opisu LIKE '%e~51%' OR tresc LIKE  '%e~51%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'o~51', 'ö'), kod_opisu = REPLACE(kod_opisu, 'o~51', 'ö') WHERE (kod_opisu LIKE '%o~51%' OR tresc LIKE  '%o~51%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'u~51', 'ü'), kod_opisu = REPLACE(kod_opisu, 'u~51', 'ü') WHERE (kod_opisu LIKE '%u~51%' OR tresc LIKE  '%u~51%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'c~11', 'ç'), kod_opisu = REPLACE(kod_opisu, 'c~11', 'ç') WHERE (kod_opisu LIKE '%c~11%' OR tresc LIKE  '%c~11%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'y~11', 'ý'), kod_opisu = REPLACE(kod_opisu, 'y~11', 'ý') WHERE (kod_opisu LIKE '%y~11%' OR tresc LIKE  '%y~11%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'r~11', 'ř'), kod_opisu = REPLACE(kod_opisu, 'r~11', 'ř') WHERE (kod_opisu LIKE '%r~11%' OR tresc LIKE  '%r~11%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'E~20', 'É'), kod_opisu = REPLACE(kod_opisu, 'E~20', 'É') WHERE (kod_opisu LIKE '%E~20%' OR tresc LIKE  '%E~20%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'C~20', 'Č'), kod_opisu = REPLACE(kod_opisu, 'C~20', 'Č') WHERE (kod_opisu LIKE '%C~20%' OR tresc LIKE  '%C~20%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'a~51', 'ä'), kod_opisu = REPLACE(kod_opisu, 'a~51', 'ä') WHERE (kod_opisu LIKE '%a~51%' OR tresc LIKE  '%a~51%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'u~41', 'ü'), kod_opisu = REPLACE(kod_opisu, 'u~41', 'ü') WHERE (tresc LIKE '%u~41%' OR kod_opisu LIKE '%u~41%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'u~40', 'ü'), kod_opisu = REPLACE(kod_opisu, 'u~40', 'ü') WHERE (tresc LIKE '%u~40%' OR kod_opisu LIKE '%u~40%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'Sjo~gren', 'Sjögren'), kod_opisu = REPLACE(kod_opisu, 'Sjo~gren', 'Sjögren') WHERE (tresc LIKE '%Sjo~gren%' OR kod_opisu LIKE '%Sjo~gren%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'e~21', 'é'), kod_opisu = REPLACE(kod_opisu, 'e~21', 'é') WHERE (tresc LIKE '%e~21%' OR kod_opisu LIKE '%e~21%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'n~21', 'ň'), kod_opisu = REPLACE(kod_opisu, 'n~21', 'ň') WHERE (tresc LIKE '%n~21%' OR kod_opisu LIKE '%n~21%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'u~21', 'ú'), kod_opisu = REPLACE(kod_opisu, 'u~21', 'ú') WHERE (tresc LIKE '%u~21%' OR kod_opisu LIKE '%u~21%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'z~11', 'ž'), kod_opisu = REPLACE(kod_opisu, 'z~11', 'ž') WHERE (tresc LIKE '%z~11%' OR kod_opisu LIKE '%z~11%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'o~81', 'ó'), kod_opisu = REPLACE(kod_opisu, 'o~81', 'ó') WHERE (tresc LIKE '%o~81%' OR kod_opisu LIKE '%o~81%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'a~81', 'ã'), kod_opisu = REPLACE(kod_opisu, 'a~81', 'ã') WHERE (tresc LIKE '%a~81%' OR kod_opisu LIKE '%a~81%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'c~21', 'č'), kod_opisu = REPLACE(kod_opisu, 'c~21', 'č') WHERE (tresc LIKE '%c~21%' OR kod_opisu LIKE '%c~21%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'e~31', 'è'), kod_opisu = REPLACE(kod_opisu, 'e~31', 'è') WHERE (tresc LIKE '%e~31%' OR kod_opisu LIKE '%e~31%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 's~31', 'š'), kod_opisu = REPLACE(kod_opisu, 's~31', 'š') WHERE (tresc LIKE '%s~31%' OR kod_opisu LIKE '%s~31%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'a~31', 'â'), kod_opisu = REPLACE(kod_opisu, 'a~31', 'â') WHERE (tresc LIKE '%a~31%' OR kod_opisu LIKE '%a~31%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'o~31', 'ô'), kod_opisu = REPLACE(kod_opisu, 'o~31', 'ô') WHERE (tresc LIKE '%o~31%' OR kod_opisu LIKE '%o~31%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'a~21', 'á'), kod_opisu = REPLACE(kod_opisu, 'a~21', 'á') WHERE (tresc LIKE '%a~21%' OR kod_opisu LIKE '%a~21%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'a~71', 'à'), kod_opisu = REPLACE(kod_opisu, 'a~71', 'à') WHERE (tresc LIKE '%a~71%' OR kod_opisu LIKE '%a~71%');


UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'i~21', 'í'), kod_opisu = REPLACE(kod_opisu, 'i~21', 'í') WHERE (tresc LIKE '%i~21%' OR kod_opisu LIKE '%i~21%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'e~41', 'ě'), kod_opisu = REPLACE(kod_opisu, 'e~41', 'ě') WHERE (tresc LIKE '%e~41%' OR kod_opisu LIKE '%e~41%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'i~41', 'ï'), kod_opisu = REPLACE(kod_opisu, 'i~41', 'ï') WHERE (tresc LIKE '%i~41%' OR kod_opisu LIKE '%i~41%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'o~41', 'ö'), kod_opisu = REPLACE(kod_opisu, 'o~41', 'ö') WHERE (tresc LIKE '%o~41%' OR kod_opisu LIKE '%o~41%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'i~61', 'ì'), kod_opisu = REPLACE(kod_opisu, 'i~61', 'ì') WHERE (tresc LIKE '%i~61%' OR kod_opisu LIKE '%i~61%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'o~21', 'ö'), kod_opisu = REPLACE(kod_opisu, 'o~21', 'ö') WHERE (tresc LIKE '%o~21%' OR kod_opisu LIKE '%o~21%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'a~91', 'ă'), kod_opisu = REPLACE(kod_opisu, 'a~91', 'ă') WHERE (tresc LIKE '%a~91%' OR kod_opisu LIKE '%a~91%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'a~61', 'ā'), kod_opisu = REPLACE(kod_opisu, 'a~61', 'ā') WHERE (tresc LIKE '%a~61%' OR kod_opisu LIKE '%a~61%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'u~61', 'ū'), kod_opisu = REPLACE(kod_opisu, 'u~61', 'ū') WHERE (tresc LIKE '%u~61%' OR kod_opisu LIKE '%u~61%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'i~31', 'î'), kod_opisu = REPLACE(kod_opisu, 'i~31', 'î') WHERE (tresc LIKE '%i~31%' OR kod_opisu LIKE '%i~31%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'u~31', 'û'), kod_opisu = REPLACE(kod_opisu, 'u~31', 'û') WHERE (tresc LIKE '%u~31%' OR kod_opisu LIKE '%u~31%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 's~41', 'ŝ'), kod_opisu = REPLACE(kod_opisu, 's~41', 'ŝ') WHERE (tresc LIKE '%s~41%' OR kod_opisu LIKE '%s~41%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'R~10', 'Ř'), kod_opisu = REPLACE(kod_opisu, 'R~10', 'Ř') WHERE (tresc LIKE '%R~10%' OR kod_opisu LIKE '%R~10%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'Z~10', 'Ž'), kod_opisu = REPLACE(kod_opisu, 'Z~10', 'Ž') WHERE (tresc LIKE '%Z~10%' OR kod_opisu LIKE '%Z~10%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'S~30', 'Š'), kod_opisu = REPLACE(kod_opisu, 'S~30', 'Š') WHERE (tresc LIKE '%S~30%' OR kod_opisu LIKE '%S~30%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'A~50', 'Ä'), kod_opisu = REPLACE(kod_opisu, 'A~50', 'Ä') WHERE (tresc LIKE '%A~50%' OR kod_opisu LIKE '%A~50%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'O~50', 'Ö'), kod_opisu = REPLACE(kod_opisu, 'O~50', 'Ö') WHERE (tresc LIKE '%O~50%' OR kod_opisu LIKE '%O~50%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'O~70', 'Ò'), kod_opisu = REPLACE(kod_opisu, 'O~70', 'Ò') WHERE (tresc LIKE '%O~70%' OR kod_opisu LIKE '%O~70%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'U~40', 'Ü'), kod_opisu = REPLACE(kod_opisu, 'U~40', 'Ü') WHERE (tresc LIKE '%U~40%' OR kod_opisu LIKE '%U~40%');
UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'U~20', 'Ú'), kod_opisu = REPLACE(kod_opisu, 'U~20', 'Ú') WHERE (tresc LIKE '%U~20%' OR kod_opisu LIKE '%U~20%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'u~91', 'ů'), kod_opisu = REPLACE(kod_opisu, 'u~91', 'ů') WHERE (tresc LIKE '%u~91%' OR kod_opisu LIKE '%u~91%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'I~60', 'Ì'), kod_opisu = REPLACE(kod_opisu, 'I~60', 'Ì') WHERE (tresc LIKE '%I~60%' OR kod_opisu LIKE '%I~60%');

UPDATE import_dbf_poz SET tresc = REPLACE(tresc, 'I~60', 'Ì'), kod_opisu = REPLACE(kod_opisu, 'I~60', 'Ì') WHERE (tresc LIKE '%I~60%' OR kod_opisu LIKE '%I~60%');

select tresc from import_dbf_poz where tresc like '%~%';



COMMIT;
