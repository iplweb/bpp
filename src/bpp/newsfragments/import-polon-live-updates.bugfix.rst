Przywrócono aktualizacje na żywo pasków postępu operacji długotrwałych
(import POLON, absencje, raporty). Brakowało autoryzatora subskrypcji
kanałów WWW (``CHANNELS_BROADCAST_SUBSCRIPTION_AUTHORIZER``), przez co
przeglądarka nie mogła zasubskrybować kanału operacji — dane importowały
się, ale pasek postępu stał, a strona nie przekierowywała po zakończeniu
(trzeba było odświeżać ręcznie). Kanał-strona operacji jest teraz
dostępny wyłącznie jej właścicielowi.
