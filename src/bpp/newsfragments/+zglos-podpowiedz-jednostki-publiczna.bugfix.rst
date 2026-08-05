W publicznym formularzu zgłaszania publikacji znów działa automatyczne
podpowiadanie jednostki i dyscypliny po wybraniu autora. Endpoint
``/bpp/api/ostatnia-jednostka-i-dyscyplina/`` przestał wymagać uprawnień
redaktorskich, zalogowania oraz tokenu CSRF — niczego nie zmienia, tylko
odczytuje dane dostępne publicznie także na stronie autora, a zgłaszać
publikacje mogą również osoby niezalogowane. Wcześniej podpowiedź znikała
po cichu (bez komunikatu), bo blokada trafiała w zapytanie AJAX.
