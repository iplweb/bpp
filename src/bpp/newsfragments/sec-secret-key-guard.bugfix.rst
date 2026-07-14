Produkcja nie uruchomi się już po cichu z placeholderowym ``SECRET_KEY``
(nieustawiona zmienna środowiskowa lub niezmieniony ``.env.docker``) —
zamiast startować z publicznie znanym kluczem (ryzyko forgowania sesji i
tokenów resetu hasła) proces przerywa start z czytelnym komunikatem.
