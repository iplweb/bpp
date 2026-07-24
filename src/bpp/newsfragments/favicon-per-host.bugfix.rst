Favicon podąża teraz za hostem w instalacji wielo-uczelnianej: każda domena
dostaje własny favicon (dotąd wszystkie uczelnie dostawały favicon site'u o
``SITE_ID``). Fragment cache faviconu w ``bare.html`` kluczowany jest per host.
Dodatkowo zapis favicona jednej uczelni nie gasi już aktywnego favicona innej
uczelni (biblioteczny ``Favicon.save`` resetował flagę globalnie po
``SITE_ID`` — teraz reset jest ograniczony do site'u zapisywanego favicona).
