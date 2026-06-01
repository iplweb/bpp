Aplikacja ``formdefaults``, dotychczas utrzymywana w drzewie BPP,
została wymieniona na zewnętrzny pakiet ``django-formdefaults``
(PyPI). Dane (``FormRepresentation``, ``FormFieldRepresentation``,
``FormFieldDefaultValue``) i utrwalone wartości domyślne pozostają
nietknięte — Django zastosuje pięć nowych migracji przyrostowo
(``pre_registered``, ``is_auto_snapshot`` plus dwa unique constraints).

Każdy formularz frontendowy zalogowanego użytkownika dostał teraz
przycisk **„Moje wartości domyślne”** w prawym górnym rogu,
otwierający popup do edycji własnych ustawień startowych pola
po polu. Użytkownicy z flagą ``is_staff`` widzą obok drugi
przycisk **„Systemowe wartości domyślne”** — edytuje on
wartość systemową, którą widzą wszyscy. Domyślne uprawnienie pakietu
(``is_superuser``) zostało rozszerzone na ``is_staff`` przez ustawienie
``FORMDEFAULTS_CAN_EDIT_SYSTEM_WIDE``.

Przyciski pojawiają się m.in. w nowych raportach, raporcie slotów,
rankingu autorów, importerze publikacji, importach (POLON, dyscypliny,
lista IF, lista ministerialna, pracownicy, udziały) oraz w wizardzie
zgłoszenia publikacji. Stary admin ``/admin/formdefaults/...`` nadal
działa.
