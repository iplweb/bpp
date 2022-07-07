Edycja danych jednostek
=======================

Pole *Aktualny wydział*
-----------------------

Pole *Aktualny wydział* jest polem tylko-do-odczytu, zaś jego wartość obliczana jest na podstawie
powiązań jednostki z wydziałem. Rozwiązane jest to w ten sposób, ponieważ jednostki mogą w niektórych
przypadkach zmieniać wydział. W takiej sytuacji można wpisać datę takiej zmiany.

Pole *Skupia pracowników*
-------------------------

Pole używane w raportach. Określa, czy jednostka skupia obecnych, aktualnych, żyjących pracowników uczelni.

W przypadku jednostek "wirtualnych" (jednostek, które faktycznie nie istnieją, a dodane do BPP zostały
celem usprawnienia zarządzania danymi) wskazane jest odznaczenie tego pola.

Pole *Zarządzaj automatycznie*
------------------------------

Pole to określa, czy dana jednostka będzie zarządzana przez system automatycznie przy imporcie danych z zewnętrznych
źródeł.

Przykładowo, jeżeli utworzymy jednostkę "wirtualną" to przy synchronizacji danych ze strukturą uczelni z zewnętrznych
źródeł danych taka jednostka nie będzie w nich występować. Zatem, przy automatycznej synchronizacji, taka jednostka
ulegałaby skasowaniu bądź zaznaczeniu, że nie jest jednostką aktualną. Zatem, dla takich jednostek, należy
odznaczyć to pole.

.. note:: W obecnym kształcie systemu BPP, pole to używane jest przy :ref:`imporcie pracowników <Import pracowników>`
    przez procedurę :ref:`odpinania nieaktualnych miejsc pracy <Odpinanie nieaktualnych miejsc pracy>`.
