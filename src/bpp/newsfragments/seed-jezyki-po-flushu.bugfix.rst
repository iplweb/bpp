Słowniki odtwarzane po transakcyjnym czyszczeniu bazy w testach obejmują
teraz także języki (``Jezyk`` wraz z ``kod_bcp47``), nie tylko rodzaje
jednostek — wcześniej test importera publikacji szukający języka po kodzie
BCP 47 potrafił paść zależnie od tego, w jakiej kolejności testy trafiły na
tego samego wykonawcę.
