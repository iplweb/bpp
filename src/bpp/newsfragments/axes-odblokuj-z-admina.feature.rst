Na liście użytkowników w panelu administracyjnym pojawiła się akcja
„Odblokuj logowanie", zdejmująca blokadę założoną po nieudanych próbach
logowania. Wcześniej wymagało to uprawnień do modeli ``axes``, których BPP
nie nadaje żadnej grupie — w praktyce odblokować mógł wyłącznie
superużytkownik albo administrator serwera z linii poleceń. Akcja radzi
sobie z blokadą zapisaną inną wielkością liter niż nazwa konta (logowanie
przez LDAP), a samo odblokowanie zapisuje się w dzienniku panelu
administracyjnego — kto i kiedy zdjął blokadę.
