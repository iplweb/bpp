BEGIN;


UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'a~00', 'α'), nazwisko = REPLACE(nazwisko, 'a~00', 'α') WHERE (imiona LIKE '%a~00%' or nazwisko LIKE '%a~00%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'b~00', 'β'), nazwisko = REPLACE(nazwisko, 'b~00', 'β') WHERE (imiona LIKE '%b~00%' or nazwisko LIKE '%b~00%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'g~00', 'γ'), nazwisko = REPLACE(nazwisko, 'g~00', 'γ') WHERE (imiona LIKE '%g~00%' or nazwisko LIKE '%g~00%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'd~00', 'δ'), nazwisko = REPLACE(nazwisko, 'd~00', 'δ') WHERE (imiona LIKE '%d~00%' or nazwisko LIKE '%d~00%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'k~00', 'κ'), nazwisko = REPLACE(nazwisko, 'k~00', 'κ') WHERE (imiona LIKE '%k~00%' or nazwisko LIKE '%k~00%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'D~00', 'Δ'), nazwisko = REPLACE(nazwisko, 'D~00', 'Δ') WHERE (imiona LIKE '%D~00%' or nazwisko LIKE '%D~00%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'w~00', 'ω'), nazwisko = REPLACE(nazwisko, 'w~00', 'ω') WHERE (imiona LIKE '%w~00%' or nazwisko LIKE '%w~00%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'W~00', 'Ω'), nazwisko = REPLACE(nazwisko, 'W~00', 'Ω') WHERE (imiona LIKE '%W~00%' or nazwisko LIKE '%W~00%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'r~00', 'ρ'), nazwisko = REPLACE(nazwisko, 'r~00', 'ρ') WHERE (imiona LIKE '%r~00%' or nazwisko LIKE '%r~00%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'm~00', 'μ'), nazwisko = REPLACE(nazwisko, 'm~00', 'μ') WHERE (imiona LIKE '%m~00%' or nazwisko LIKE '%m~00%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'e~00', 'ε'), nazwisko = REPLACE(nazwisko, 'e~00', 'ε') WHERE (imiona LIKE '%e~00%' or nazwisko LIKE '%e~00%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'z~00', 'ζ'), nazwisko = REPLACE(nazwisko, 'z~00', 'ζ') WHERE (imiona LIKE '%z~00%' or nazwisko LIKE '%z~00%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'p~00', 'π'), nazwisko = REPLACE(nazwisko, 'p~00', 'π') WHERE (imiona LIKE '%p~00%' or nazwisko LIKE '%p~00%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'j~00', 'θ'), nazwisko = REPLACE(nazwisko, 'j~00', 'θ') WHERE (imiona LIKE '%j~00%' or nazwisko LIKE '%j~00%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'l~00', 'λ'), nazwisko = REPLACE(nazwisko, 'l~00', 'λ') WHERE (imiona LIKE '%l~00%' or nazwisko LIKE '%l~00%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'l~~00', 'λ'), nazwisko = REPLACE(nazwisko, 'l~~00', 'λ') WHERE (imiona LIKE '%l~~00%' or nazwisko LIKE '%l~~00%');


UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'e~51', 'ë'), nazwisko = REPLACE(nazwisko, 'e~51', 'ë') WHERE (nazwisko LIKE '%e~51%' OR imiona LIKE  '%e~51%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'o~51', 'ö'), nazwisko = REPLACE(nazwisko, 'o~51', 'ö') WHERE (nazwisko LIKE '%o~51%' OR imiona LIKE  '%o~51%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'u~51', 'ü'), nazwisko = REPLACE(nazwisko, 'u~51', 'ü') WHERE (nazwisko LIKE '%u~51%' OR imiona LIKE  '%u~51%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'c~11', 'ç'), nazwisko = REPLACE(nazwisko, 'c~11', 'ç') WHERE (nazwisko LIKE '%c~11%' OR imiona LIKE  '%c~11%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'y~11', 'ý'), nazwisko = REPLACE(nazwisko, 'y~11', 'ý') WHERE (nazwisko LIKE '%y~11%' OR imiona LIKE  '%y~11%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'r~11', 'ř'), nazwisko = REPLACE(nazwisko, 'r~11', 'ř') WHERE (nazwisko LIKE '%r~11%' OR imiona LIKE  '%r~11%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'E~20', 'É'), nazwisko = REPLACE(nazwisko, 'E~20', 'É') WHERE (nazwisko LIKE '%E~20%' OR imiona LIKE  '%E~20%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'C~20', 'Č'), nazwisko = REPLACE(nazwisko, 'C~20', 'Č') WHERE (nazwisko LIKE '%C~20%' OR imiona LIKE  '%C~20%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'a~51', 'ä'), nazwisko = REPLACE(nazwisko, 'a~51', 'ä') WHERE (nazwisko LIKE '%a~51%' OR imiona LIKE  '%a~51%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'u~41', 'ü'), nazwisko = REPLACE(nazwisko, 'u~41', 'ü') WHERE (imiona LIKE '%u~41%' OR nazwisko LIKE '%u~41%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'u~40', 'ü'), nazwisko = REPLACE(nazwisko, 'u~40', 'ü') WHERE (imiona LIKE '%u~40%' OR nazwisko LIKE '%u~40%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'Sjo~gren', 'Sjögren'), nazwisko = REPLACE(nazwisko, 'Sjo~gren', 'Sjögren') WHERE (imiona LIKE '%Sjo~gren%' OR nazwisko LIKE '%Sjo~gren%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'e~21', 'é'), nazwisko = REPLACE(nazwisko, 'e~21', 'é') WHERE (imiona LIKE '%e~21%' OR nazwisko LIKE '%e~21%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'n~21', 'ň'), nazwisko = REPLACE(nazwisko, 'n~21', 'ň') WHERE (imiona LIKE '%n~21%' OR nazwisko LIKE '%n~21%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'u~21', 'ú'), nazwisko = REPLACE(nazwisko, 'u~21', 'ú') WHERE (imiona LIKE '%u~21%' OR nazwisko LIKE '%u~21%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'z~11', 'ž'), nazwisko = REPLACE(nazwisko, 'z~11', 'ž') WHERE (imiona LIKE '%z~11%' OR nazwisko LIKE '%z~11%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'o~81', 'ó'), nazwisko = REPLACE(nazwisko, 'o~81', 'ó') WHERE (imiona LIKE '%o~81%' OR nazwisko LIKE '%o~81%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'a~81', 'ã'), nazwisko = REPLACE(nazwisko, 'a~81', 'ã') WHERE (imiona LIKE '%a~81%' OR nazwisko LIKE '%a~81%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'c~21', 'č'), nazwisko = REPLACE(nazwisko, 'c~21', 'č') WHERE (imiona LIKE '%c~21%' OR nazwisko LIKE '%c~21%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'e~31', 'è'), nazwisko = REPLACE(nazwisko, 'e~31', 'è') WHERE (imiona LIKE '%e~31%' OR nazwisko LIKE '%e~31%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 's~31', 'š'), nazwisko = REPLACE(nazwisko, 's~31', 'š') WHERE (imiona LIKE '%s~31%' OR nazwisko LIKE '%s~31%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'a~31', 'â'), nazwisko = REPLACE(nazwisko, 'a~31', 'â') WHERE (imiona LIKE '%a~31%' OR nazwisko LIKE '%a~31%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'o~31', 'ô'), nazwisko = REPLACE(nazwisko, 'o~31', 'ô') WHERE (imiona LIKE '%o~31%' OR nazwisko LIKE '%o~31%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'a~21', 'á'), nazwisko = REPLACE(nazwisko, 'a~21', 'á') WHERE (imiona LIKE '%a~21%' OR nazwisko LIKE '%a~21%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'a~71', 'à'), nazwisko = REPLACE(nazwisko, 'a~71', 'à') WHERE (imiona LIKE '%a~71%' OR nazwisko LIKE '%a~71%');


UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'i~21', 'í'), nazwisko = REPLACE(nazwisko, 'i~21', 'í') WHERE (imiona LIKE '%i~21%' OR nazwisko LIKE '%i~21%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'e~41', 'ě'), nazwisko = REPLACE(nazwisko, 'e~41', 'ě') WHERE (imiona LIKE '%e~41%' OR nazwisko LIKE '%e~41%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'i~41', 'ï'), nazwisko = REPLACE(nazwisko, 'i~41', 'ï') WHERE (imiona LIKE '%i~41%' OR nazwisko LIKE '%i~41%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'o~41', 'ö'), nazwisko = REPLACE(nazwisko, 'o~41', 'ö') WHERE (imiona LIKE '%o~41%' OR nazwisko LIKE '%o~41%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'i~61', 'ì'), nazwisko = REPLACE(nazwisko, 'i~61', 'ì') WHERE (imiona LIKE '%i~61%' OR nazwisko LIKE '%i~61%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'I~60', 'Ì'), nazwisko = REPLACE(nazwisko, 'I~60', 'Ì') WHERE (imiona LIKE '%I~60%' OR nazwisko LIKE '%I~60%');


UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'o~21', 'ö'), nazwisko = REPLACE(nazwisko, 'o~21', 'ö') WHERE (imiona LIKE '%o~21%' OR nazwisko LIKE '%o~21%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'a~91', 'ă'), nazwisko = REPLACE(nazwisko, 'a~91', 'ă') WHERE (imiona LIKE '%a~91%' OR nazwisko LIKE '%a~91%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'a~61', 'ā'), nazwisko = REPLACE(nazwisko, 'a~61', 'ā') WHERE (imiona LIKE '%a~61%' OR nazwisko LIKE '%a~61%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'u~61', 'ū'), nazwisko = REPLACE(nazwisko, 'u~61', 'ū') WHERE (imiona LIKE '%u~61%' OR nazwisko LIKE '%u~61%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'i~31', 'î'), nazwisko = REPLACE(nazwisko, 'i~31', 'î') WHERE (imiona LIKE '%i~31%' OR nazwisko LIKE '%i~31%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'u~31', 'û'), nazwisko = REPLACE(nazwisko, 'u~31', 'û') WHERE (imiona LIKE '%u~31%' OR nazwisko LIKE '%u~31%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 's~41', 'ŝ'), nazwisko = REPLACE(nazwisko, 's~41', 'ŝ') WHERE (imiona LIKE '%s~41%' OR nazwisko LIKE '%s~41%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'R~10', 'Ř'), nazwisko = REPLACE(nazwisko, 'R~10', 'Ř') WHERE (imiona LIKE '%R~10%' OR nazwisko LIKE '%R~10%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'Z~10', 'Ž'), nazwisko = REPLACE(nazwisko, 'Z~10', 'Ž') WHERE (imiona LIKE '%Z~10%' OR nazwisko LIKE '%Z~10%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'S~30', 'Š'), nazwisko = REPLACE(nazwisko, 'S~30', 'Š') WHERE (imiona LIKE '%S~30%' OR nazwisko LIKE '%S~30%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'A~50', 'Ä'), nazwisko = REPLACE(nazwisko, 'A~50', 'Ä') WHERE (imiona LIKE '%A~50%' OR nazwisko LIKE '%A~50%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'O~50', 'Ö'), nazwisko = REPLACE(nazwisko, 'O~50', 'Ö') WHERE (imiona LIKE '%O~50%' OR nazwisko LIKE '%O~50%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'O~70', 'Ò'), nazwisko = REPLACE(nazwisko, 'O~70', 'Ò') WHERE (imiona LIKE '%O~70%' OR nazwisko LIKE '%O~70%');
UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'U~40', 'Ü'), nazwisko = REPLACE(nazwisko, 'U~40', 'Ü') WHERE (imiona LIKE '%U~40%' OR nazwisko LIKE '%U~40%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'u~91', 'ů'), nazwisko = REPLACE(nazwisko, 'u~91', 'ů') WHERE (imiona LIKE '%u~91%' OR nazwisko LIKE '%u~91%');



UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 's~21', 'ş'), nazwisko = REPLACE(nazwisko, 's~21', 'ş') WHERE (imiona LIKE '%s~21%' OR nazwisko LIKE '%s~21%');

UPDATE import_dbf_aut SET imiona = REPLACE(imiona, 'U~30', 'Û'), nazwisko = REPLACE(nazwisko, 'U~30', 'Û') WHERE (imiona LIKE '%U~30%' OR nazwisko LIKE '%U~30%');


--  Bilo~71
--  B~51hm


select nazwisko from import_dbf_aut where nazwisko like '%~%';
select imiona from import_dbf_aut where imiona like '%~%';



COMMIT;
