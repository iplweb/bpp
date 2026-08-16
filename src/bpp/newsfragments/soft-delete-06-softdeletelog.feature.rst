Operacje usuwania rekordów do kosza, przywracania ich i kasowania trwale są
odtąd zapisywane w dzienniku „Log operacji soft-delete": kto, kiedy, z jakim
powodem oraz czy zlecono wycofanie lub ponowną wysyłkę oświadczeń do PBN.
Wrzucenie pracy do kosza usuwa też jej punktację z pamięci podręcznej
ewaluacji (praca w koszu nie wnosi już slotów ani punktów), a przywrócenie
przelicza ją na nowo.
