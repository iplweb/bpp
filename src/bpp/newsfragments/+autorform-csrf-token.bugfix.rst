Naprawiono auto-uzupełnianie jednostki i dyscypliny przy dodawaniu
autora w publicznym formularzu „Zgłoś publikację”. Skrypt
``autorform_dependant.js`` wysyłał POST do
``/bpp/api/ostatnia-jednostka-i-dyscyplina/`` bez tokenu CSRF —
publiczne ``base.html`` (w przeciwieństwie do admin-owego) nie ma
globalnego ``$.ajaxSetup`` dodającego nagłówek ``X-CSRFToken``,
więc żądanie kończyło się odpowiedzią 403 i pola nie były
wypełniane. Skrypt czyta teraz ``csrfmiddlewaretoken`` z ukrytego
pola formularza i dokleja go do danych żądania.
