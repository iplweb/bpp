Formularz logowania serwera uwierzytelniania (``authserver``, brama SSO do
Grafany, Dozzle, Flowera i Netdaty) nie twierdzi już, że jest logowaniem
awaryjnym ani że "system jest w trakcie uruchamiania" — żadne z tych zdań nie
było prawdziwe: to zwykła ścieżka logowania do narzędzi administracyjnych.
Strona nazywa się teraz "Logowanie do BPP" i jest napisana po polsku
z diakrytykami. Zalogowany użytkownik bez uprawnień administratora zamiast
generycznego błędu 403 webserwera dostaje stronę z wyjaśnieniem, na jakie konto
jest zalogowany, i przyciskiem wylogowania.
