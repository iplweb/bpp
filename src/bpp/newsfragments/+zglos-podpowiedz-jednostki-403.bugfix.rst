Formularz „Zgłoś publikację" znów podpowiada jednostkę i dyscyplinę autora.
Endpoint ``/bpp/api/ostatnia-jednostka-i-dyscyplina/`` — który tylko czyta dane
i niczego nie zapisuje — trafił przez pomyłkę pod bramkę uprawnień
redaktorskich, więc każdy zgłaszający bez roli redaktora dostawał w tle błąd
403 i tracił podpowiedź (po cichu, bo to zapytanie AJAX). Wymagane pozostaje
samo zalogowanie.
