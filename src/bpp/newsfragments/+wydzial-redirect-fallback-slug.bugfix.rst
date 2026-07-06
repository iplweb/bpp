Adres ``/bpp/wydzial/<slug>/`` przekierowuje teraz także wtedy, gdy
slug nie odpowiada żadnemu dawnemu wydziałowi, ale istnieje jednostka
o dokładnie tym slugu (np. wydział założony od razu w drzewie
jednostek) — użytkownik trafia wówczas wprost na
``/bpp/jednostka/<ten-sam-slug>/``. Dotychczasowe przekierowania
dawnych wydziałów na ich węzły-lustra działają bez zmian; nieznane
slugi nadal zwracają 404.
