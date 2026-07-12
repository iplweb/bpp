Import PBN: naprawiono obsługę błędu zapisu statusu sesji — wcześniej ``except
BaseException`` połykał przerwania workera (KeyboardInterrupt/SystemExit), a
następujący po nim ``except Exception`` był martwym, nieosiągalnym kodem. Teraz
łapany jest wyłącznie ``Exception`` (przerwania się propagują), a nieudany
zapis błędu jest logowany z tracebackiem i zgłaszany do Rollbara.
