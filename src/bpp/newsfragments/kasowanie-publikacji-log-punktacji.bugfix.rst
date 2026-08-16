Kasowanie publikacji nie jest już blokowane komunikatem o braku uprawnień do
usunięcia obiektu „log zmiany punktacji". Django admin sprawdza uprawnienie do
usunięcia każdego obiektu kasowanego kaskadowo, a admin logu rozbieżności
odmawiał go bezwarunkowo — również superuserowi — więc żadnego wydawnictwa
ciągłego, do którego powstał wpis w logu, nie dało się skasować. Log nadal
pozostaje niemodyfikowalny (nie można go dopisać ani zmienić), a redakcja
otrzymała uprawnienia do modeli aplikacji rozbieżności, żeby kasowanie
publikacji działało także dla użytkowników spoza grupy administracyjnej.
