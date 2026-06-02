Dodano interaktywne narzędzie CLI
``pbn_test_wysylka_interaktywna`` (Django management command) do
eksperymentalnego testowania flow wysyłki publikacji i oświadczeń do PBN
krok po kroku. Narzędzie prowadzi użytkownika przez kolejne fazy —
generowanie JSON publikacji, wybór endpointa (``/api/v1/publications``
all-in-one albo ``/api/v1/repositorium/publications`` bez oświadczeń),
POST publikacji, GET i porównanie oświadczeń lokalnych z tym co jest w
PBN, DELETE oświadczeń i POST przez ``/api/v2/institution-profile/statements``
— pokazując dla każdego kroku metodę HTTP, URL, body i odpowiedź
serwera. Narzędzie nie modyfikuje lokalnej bazy BPP i posiada tryb
``--dry-run``. Służy jako baza do audytu zachowania PBN API i
projektowania bezpieczniejszej kolejności operacji wysyłki (scenariusz:
nieudana wysyłka publikacji kasowała wcześniej istniejące oświadczenia).
