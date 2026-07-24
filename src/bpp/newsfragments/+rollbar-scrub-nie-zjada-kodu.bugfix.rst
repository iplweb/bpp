Zgłoszenia błędów wysyłane do monitoringu znów zawierają linie kodu
w miejscu awarii. Reguła maskowania danych wrażliwych obejmowała pole o nazwie
``code`` — a pod tą samą nazwą biblioteka monitoringu przechowuje linię kodu
źródłowego każdej ramki śladu wywołań. Od jednej z ostatnich aktualizacji
skutkowało to zamazaniem całych śladów wywołań, co utrudniało diagnostykę.
Kod autoryzacyjny OAuth jest nadal maskowany.
