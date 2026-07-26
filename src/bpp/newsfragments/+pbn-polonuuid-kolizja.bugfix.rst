Import osób z API instytucji PBN radzi sobie z osobami, którym PBN zmienił
identyfikator. ``polonUuid`` (identyfikator z POL-onu) jest stabilną
tożsamością osoby, a ``personId`` PBN potrafi zmienić — np. po scaleniu
zdublowanych profili. Import dopasowywał wpis wyłącznie po ``personId``,
więc taka osoba rozbijała się o unikalność ``polonUuid`` i była pomijana;
teraz jej wpis jest przepinany na nowy identyfikator. Osoby bez
``polonUuid`` są pomijane z czytelnym komunikatem w logu, zamiast trafiać
do monitoringu jako „konflikt tożsamości".
