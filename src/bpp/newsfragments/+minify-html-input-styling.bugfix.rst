Pole „Nazwa użytkownika" na stronie ``/accounts/login/`` było
wyświetlane bez stylu Foundation — wąskie, niskie, wyraźnie inne
niż pole „Hasło". Przyczyną była agresywna minifikacja HTML przez
``django-minify-html`` usuwająca atrybut ``type="text"`` (domyślny
w HTML5), do którego odwołuje się Foundation 6 przez selektor
``input[type="text"]``. Po skonfigurowaniu middleware z opcją
``keep_input_type_text_attr=True`` atrybut jest zachowywany i pole
wygląda tak samo jak pozostałe pola tekstowe w systemie.

Dodatkowo włączono ``keep_closing_tags=True`` — treści z bazy
(np. znacznik ``<jats:p>`` w abstraktach publikacji) po zrzuceniu
opcjonalnych ``</li>``/``</p>`` potrafiły rozjechać drzewo DOM
i przesłaniać stopkę na stronie głównej.

Zaktualizowano rok w stopce na 2026.
