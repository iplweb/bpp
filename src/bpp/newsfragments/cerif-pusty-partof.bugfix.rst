Eksport CERIF/OpenAIRE: jednostka, której jednostka nadrzędna jest wyłączona
z eksportu (``widoczna=False`` albo ``nie_eksportuj_przez_api``), nie zostawia
już pustego elementu ``PartOf``. Pusty ``PartOf`` jest niepoprawny wobec
schematu profilu, a walidator euroCRIS przerywał na nim harvest całego zestawu
``openaire_cris_orgunits`` — przez co kolejne jednostki nie trafiały do indeksu
i ich powiązania z publikacji wyglądały na wiszące (dwa błędy walidatora
z jednej przyczyny). Taka jednostka jest teraz podpinana pod uczelnię, więc
drzewo organizacyjne pozostaje spójne, a o ukrytej jednostce nadrzędnej nadal
nic nie wychodzi na zewnątrz.
