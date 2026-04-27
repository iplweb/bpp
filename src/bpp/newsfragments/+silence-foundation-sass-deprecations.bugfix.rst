Wyciszono ``if-function`` w Dart Sass podczas ``make assets`` — wewnętrzne
ostrzeżenia z foundation-sites 6.9.0 (util/_value.scss, _breakpoint.scss,
_color.scss, _flex.scss, _math.scss), nieusuwalne z poziomu naszego repo,
ponieważ Foundation jest w trybie maintenance. Komentarz w
``Gruntfile.js`` wyjaśnia, dlaczego każda z trzech kategorii
(``global-builtin``, ``if-function``, ``import``) jest na liście
``silenceDeprecations``. Liczba ostrzeżeń budowy spadła z 50 do 0.
