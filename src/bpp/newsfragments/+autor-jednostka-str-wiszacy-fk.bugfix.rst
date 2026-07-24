Kasowanie autora nie zgłasza już do monitoringu błędów fałszywego alarmu.
Podczas kaskadowego usuwania Django buduje opis tekstowy powiązania
autor–jednostka, którego dane właśnie zniknęły; ten spodziewany przypadek
trafiał do monitoringu jako błąd aplikacji. Zachowanie samego kasowania się
nie zmienia.
