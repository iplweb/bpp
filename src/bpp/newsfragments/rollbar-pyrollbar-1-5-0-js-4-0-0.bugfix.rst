Zaktualizowano monitoring błędów Rollbar: biblioteka serwerowa ``pyrollbar``
do wersji 1.5.0, a przeglądarkowa ``rollbar.js`` do 4.0.0. Nowe wydanie
przeglądarkowe ogranicza rozrost danych telemetrycznych na długo otwartych
kartach; porzucone w nim wsparcie dla Node 18 nie ma wpływu na BPP, bo statyki
budowane są na Node 20. Konfiguracja nie wymagała zmian — filtr zgłoszeń
``checkIgnore`` oraz własne transformy zamazujące kod autoryzacyjny OAuth
działają bez modyfikacji.
