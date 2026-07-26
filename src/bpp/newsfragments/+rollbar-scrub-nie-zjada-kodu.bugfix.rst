Zgłoszenia błędów wysyłane do monitoringu znów zawierają linie kodu w miejscu
awarii. Reguła maskowania danych wrażliwych obejmowała pole o nazwie ``code``,
a pod tą samą nazwą biblioteka monitoringu przechowuje linię kodu źródłowego
każdej ramki śladu wywołań — od 11 lipca 2026 skutkowało to zamazywaniem
całych śladów wywołań i utrudniało diagnostykę. Kody autoryzacyjne OAuth są
nadal maskowane, również w adresach URL i zmiennych lokalnych.
