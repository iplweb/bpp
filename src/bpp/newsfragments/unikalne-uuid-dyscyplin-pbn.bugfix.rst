Naprawiono błąd, przez który import słownika dyscyplin z PBN mógł zablokować
się trwale. Brak unikalności UUID-ów powodował, że dwa równoległe importy
tworzyły zduplikowany słownik lub dyscyplinę, a od tego momentu każdy kolejny
import przerywał się błędem ``MultipleObjectsReturned`` — aż do ręcznego
uporządkowania bazy danych. Migracja scala istniejące duplikaty (przepinając
powiązania tłumacza dyscyplin) i zakłada brakujące ograniczenia unikalności.
