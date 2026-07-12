Aktualizacja liczby cytowań z Web of Science działa teraz hurtowo. Wcześniej
dla każdej uczelni ponownie przechodzono cały korpus, a każdy zmieniony rekord
był doczytywany (``get()``) i zapisywany (``save()``) osobno. Teraz korpus jest
odpytywany raz na typ publikacji, wyniki wszystkich klientów WoS są scalane,
rekordy doczytywane jednym zapytaniem, a zapis idzie jednym ``bulk_update`` —
znacznie mniej zapytań do bazy przy dużym korpusie.
