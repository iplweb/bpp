BEGIN;


UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'a~00', 'α'), skrot = REPLACE(skrot, 'a~00', 'α') WHERE (nazwa LIKE '%a~00%' or skrot LIKE '%a~00%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'b~00', 'β'), skrot = REPLACE(skrot, 'b~00', 'β') WHERE (nazwa LIKE '%b~00%' or skrot LIKE '%b~00%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'g~00', 'γ'), skrot = REPLACE(skrot, 'g~00', 'γ') WHERE (nazwa LIKE '%g~00%' or skrot LIKE '%g~00%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'd~00', 'δ'), skrot = REPLACE(skrot, 'd~00', 'δ') WHERE (nazwa LIKE '%d~00%' or skrot LIKE '%d~00%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'k~00', 'κ'), skrot = REPLACE(skrot, 'k~00', 'κ') WHERE (nazwa LIKE '%k~00%' or skrot LIKE '%k~00%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'D~00', 'Δ'), skrot = REPLACE(skrot, 'D~00', 'Δ') WHERE (nazwa LIKE '%D~00%' or skrot LIKE '%D~00%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'w~00', 'ω'), skrot = REPLACE(skrot, 'w~00', 'ω') WHERE (nazwa LIKE '%w~00%' or skrot LIKE '%w~00%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'W~00', 'Ω'), skrot = REPLACE(skrot, 'W~00', 'Ω') WHERE (nazwa LIKE '%W~00%' or skrot LIKE '%W~00%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'r~00', 'ρ'), skrot = REPLACE(skrot, 'r~00', 'ρ') WHERE (nazwa LIKE '%r~00%' or skrot LIKE '%r~00%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'm~00', 'μ'), skrot = REPLACE(skrot, 'm~00', 'μ') WHERE (nazwa LIKE '%m~00%' or skrot LIKE '%m~00%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'e~00', 'ε'), skrot = REPLACE(skrot, 'e~00', 'ε') WHERE (nazwa LIKE '%e~00%' or skrot LIKE '%e~00%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'z~00', 'ζ'), skrot = REPLACE(skrot, 'z~00', 'ζ') WHERE (nazwa LIKE '%z~00%' or skrot LIKE '%z~00%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'p~00', 'π'), skrot = REPLACE(skrot, 'p~00', 'π') WHERE (nazwa LIKE '%p~00%' or skrot LIKE '%p~00%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'j~00', 'θ'), skrot = REPLACE(skrot, 'j~00', 'θ') WHERE (nazwa LIKE '%j~00%' or skrot LIKE '%j~00%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'l~00', 'λ'), skrot = REPLACE(skrot, 'l~00', 'λ') WHERE (nazwa LIKE '%l~00%' or skrot LIKE '%l~00%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'l~~00', 'λ'), skrot = REPLACE(skrot, 'l~~00', 'λ') WHERE (nazwa LIKE '%l~~00%' or skrot LIKE '%l~~00%');


UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'e~51', 'ë'), skrot = REPLACE(skrot, 'e~51', 'ë') WHERE (skrot LIKE '%e~51%' OR nazwa LIKE  '%e~51%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'o~51', 'ö'), skrot = REPLACE(skrot, 'o~51', 'ö') WHERE (skrot LIKE '%o~51%' OR nazwa LIKE  '%o~51%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'u~51', 'ü'), skrot = REPLACE(skrot, 'u~51', 'ü') WHERE (skrot LIKE '%u~51%' OR nazwa LIKE  '%u~51%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'c~11', 'ç'), skrot = REPLACE(skrot, 'c~11', 'ç') WHERE (skrot LIKE '%c~11%' OR nazwa LIKE  '%c~11%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'y~11', 'ý'), skrot = REPLACE(skrot, 'y~11', 'ý') WHERE (skrot LIKE '%y~11%' OR nazwa LIKE  '%y~11%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'r~11', 'ř'), skrot = REPLACE(skrot, 'r~11', 'ř') WHERE (skrot LIKE '%r~11%' OR nazwa LIKE  '%r~11%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'E~20', 'É'), skrot = REPLACE(skrot, 'E~20', 'É') WHERE (skrot LIKE '%E~20%' OR nazwa LIKE  '%E~20%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'C~20', 'Č'), skrot = REPLACE(skrot, 'C~20', 'Č') WHERE (skrot LIKE '%C~20%' OR nazwa LIKE  '%C~20%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'a~51', 'ä'), skrot = REPLACE(skrot, 'a~51', 'ä') WHERE (skrot LIKE '%a~51%' OR nazwa LIKE  '%a~51%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'u~41', 'ü'), skrot = REPLACE(skrot, 'u~41', 'ü') WHERE (nazwa LIKE '%u~41%' OR skrot LIKE '%u~41%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'u~40', 'ü'), skrot = REPLACE(skrot, 'u~40', 'ü') WHERE (nazwa LIKE '%u~40%' OR skrot LIKE '%u~40%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'Sjo~gren', 'Sjögren'), skrot = REPLACE(skrot, 'Sjo~gren', 'Sjögren') WHERE (nazwa LIKE '%Sjo~gren%' OR skrot LIKE '%Sjo~gren%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'e~21', 'é'), skrot = REPLACE(skrot, 'e~21', 'é') WHERE (nazwa LIKE '%e~21%' OR skrot LIKE '%e~21%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'n~21', 'ň'), skrot = REPLACE(skrot, 'n~21', 'ň') WHERE (nazwa LIKE '%n~21%' OR skrot LIKE '%n~21%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'u~21', 'ú'), skrot = REPLACE(skrot, 'u~21', 'ú') WHERE (nazwa LIKE '%u~21%' OR skrot LIKE '%u~21%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'z~11', 'ž'), skrot = REPLACE(skrot, 'z~11', 'ž') WHERE (nazwa LIKE '%z~11%' OR skrot LIKE '%z~11%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'o~81', 'ó'), skrot = REPLACE(skrot, 'o~81', 'ó') WHERE (nazwa LIKE '%o~81%' OR skrot LIKE '%o~81%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'a~81', 'ã'), skrot = REPLACE(skrot, 'a~81', 'ã') WHERE (nazwa LIKE '%a~81%' OR skrot LIKE '%a~81%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'c~21', 'č'), skrot = REPLACE(skrot, 'c~21', 'č') WHERE (nazwa LIKE '%c~21%' OR skrot LIKE '%c~21%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'e~31', 'è'), skrot = REPLACE(skrot, 'e~31', 'è') WHERE (nazwa LIKE '%e~31%' OR skrot LIKE '%e~31%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 's~31', 'š'), skrot = REPLACE(skrot, 's~31', 'š') WHERE (nazwa LIKE '%s~31%' OR skrot LIKE '%s~31%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'a~31', 'â'), skrot = REPLACE(skrot, 'a~31', 'â') WHERE (nazwa LIKE '%a~31%' OR skrot LIKE '%a~31%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'o~31', 'ô'), skrot = REPLACE(skrot, 'o~31', 'ô') WHERE (nazwa LIKE '%o~31%' OR skrot LIKE '%o~31%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'a~21', 'á'), skrot = REPLACE(skrot, 'a~21', 'á') WHERE (nazwa LIKE '%a~21%' OR skrot LIKE '%a~21%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'a~71', 'à'), skrot = REPLACE(skrot, 'a~71', 'à') WHERE (nazwa LIKE '%a~71%' OR skrot LIKE '%a~71%');


UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'i~21', 'í'), skrot = REPLACE(skrot, 'i~21', 'í') WHERE (nazwa LIKE '%i~21%' OR skrot LIKE '%i~21%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'e~41', 'ě'), skrot = REPLACE(skrot, 'e~41', 'ě') WHERE (nazwa LIKE '%e~41%' OR skrot LIKE '%e~41%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'i~41', 'ï'), skrot = REPLACE(skrot, 'i~41', 'ï') WHERE (nazwa LIKE '%i~41%' OR skrot LIKE '%i~41%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'o~41', 'ö'), skrot = REPLACE(skrot, 'o~41', 'ö') WHERE (nazwa LIKE '%o~41%' OR skrot LIKE '%o~41%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'i~61', 'ì'), skrot = REPLACE(skrot, 'i~61', 'ì') WHERE (nazwa LIKE '%i~61%' OR skrot LIKE '%i~61%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'o~21', 'ö'), skrot = REPLACE(skrot, 'o~21', 'ö') WHERE (nazwa LIKE '%o~21%' OR skrot LIKE '%o~21%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'a~91', 'ă'), skrot = REPLACE(skrot, 'a~91', 'ă') WHERE (nazwa LIKE '%a~91%' OR skrot LIKE '%a~91%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'a~61', 'ā'), skrot = REPLACE(skrot, 'a~61', 'ā') WHERE (nazwa LIKE '%a~61%' OR skrot LIKE '%a~61%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'u~61', 'ū'), skrot = REPLACE(skrot, 'u~61', 'ū') WHERE (nazwa LIKE '%u~61%' OR skrot LIKE '%u~61%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'i~31', 'î'), skrot = REPLACE(skrot, 'i~31', 'î') WHERE (nazwa LIKE '%i~31%' OR skrot LIKE '%i~31%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'u~31', 'û'), skrot = REPLACE(skrot, 'u~31', 'û') WHERE (nazwa LIKE '%u~31%' OR skrot LIKE '%u~31%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 's~41', 'ŝ'), skrot = REPLACE(skrot, 's~41', 'ŝ') WHERE (nazwa LIKE '%s~41%' OR skrot LIKE '%s~41%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'R~10', 'Ř'), skrot = REPLACE(skrot, 'R~10', 'Ř') WHERE (nazwa LIKE '%R~10%' OR skrot LIKE '%R~10%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'Z~10', 'Ž'), skrot = REPLACE(skrot, 'Z~10', 'Ž') WHERE (nazwa LIKE '%Z~10%' OR skrot LIKE '%Z~10%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'S~30', 'Š'), skrot = REPLACE(skrot, 'S~30', 'Š') WHERE (nazwa LIKE '%S~30%' OR skrot LIKE '%S~30%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'A~50', 'Ä'), skrot = REPLACE(skrot, 'A~50', 'Ä') WHERE (nazwa LIKE '%A~50%' OR skrot LIKE '%A~50%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'O~50', 'Ö'), skrot = REPLACE(skrot, 'O~50', 'Ö') WHERE (nazwa LIKE '%O~50%' OR skrot LIKE '%O~50%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'O~70', 'Ò'), skrot = REPLACE(skrot, 'O~70', 'Ò') WHERE (nazwa LIKE '%O~70%' OR skrot LIKE '%O~70%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'U~40', 'Ü'), skrot = REPLACE(skrot, 'U~40', 'Ü') WHERE (nazwa LIKE '%U~40%' OR skrot LIKE '%U~40%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'U~20', 'Ú'), skrot = REPLACE(skrot, 'U~20', 'Ú') WHERE (nazwa LIKE '%U~20%' OR skrot LIKE '%U~20%');

UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'u~91', 'ů'), skrot = REPLACE(skrot, 'u~91', 'ů') WHERE (nazwa LIKE '%u~91%' OR skrot LIKE '%u~91%');



UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'Y~10', 'Ý'), skrot = REPLACE(skrot, 'Y~10', 'Ý') WHERE (nazwa LIKE '%Y~10%' OR skrot LIKE '%Y~10%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 'c~31', 'č'), skrot = REPLACE(skrot, 'c~31', 'č') WHERE (nazwa LIKE '%c~31%' OR skrot LIKE '%c~31%');
UPDATE import_dbf_usi SET nazwa = REPLACE(nazwa, 's~21', 'ş'), skrot = REPLACE(skrot, 's~21', 'ş') WHERE (nazwa LIKE '%s~21%' OR skrot LIKE '%s~21%');

select nazwa from import_dbf_usi where nazwa like '%~%';



COMMIT;
