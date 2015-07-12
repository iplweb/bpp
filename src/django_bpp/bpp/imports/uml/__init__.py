# -*- encoding: utf-8 -*-


class UML_Egeria_2012_Mangle:
    """Klasa zawierająca informacje, w jaki sposób potraktować nazwy jednostek, ciągi znaków,
    zawarte w importowanym pliku XLS"""

    # Tych jednostek nie importujemy z pliku wejściowego XLS
    ignorowane_jednostki = [
        u'Katedra Chemii',
        u'Katedra Diagnostyki Laboratoryjnej',
        u'Sam. Pracownia Propedeutyki Radiologii Stom. i Szczęk-Twarz',
        u'Pracownia Spektrometrii Absorpcji Atomowej',
        u'Klinika Endokrynologii i Neurologii Dziecięcej',
        u'Pracownia Zarządzania i Ekonomiki Farmaceutycznej',
        u'Pracownia Otoneurologiczna',
        u'Zakład Elektroradiologii',
        u'Pracownia Toksykologii Sądowej',
        u'Pracownia Farmakologii Komórkowej i Molekularnej',
        u'Pracownia Analizy DNA i Diagnostyki Molekularnej'
        u'Samodzielna Pracownia Zdrowia Psychicznego',
        u'Zakład Podstaw Pielęgniarstwa i Dydaktyki Medycznej'
    ]

    # W przypadku tych jednostek odpytujemy BEZPOŚREDNIO o nazwę tej jednostki,
    # ponieważ odpytanie standardowe zwróciłoby zbyt dużą ilość jednostek.
    # Ponieważ kliniki mają na początku rzymskie numerki, to icontains
    # znajdzie II katedrę w IIIciej, więc:
    single_fitters = [
        u'Zakład Farmakologii',
        u'I Katedra i Klinika Ginekologii',
        u'II Katedra i Klinika Ginekologii',
        u'III Katedra i Klinika Ginekologii',
        ]

    # To zamiany nazw jednostek z tych, które są w XLSie na te, które mamy w BPP
    zamiany_nazw_jednostek = {

        u'Katedra i Klinika Ginekologii i Endokrynologii Ginekolog.':
            u'Katedra i Klinika Ginekologii i Endokrynologii Ginekologicznej',

        u'Zakład Położn., Ginekol. i Pielęg. Położ-Ginekolog.':
            u'Zakład Położnictwa, Ginekologii i Pielęgniarstwa Położniczo-Ginekologicznego',

        u'Zakład Pielęgniarstwa Anestezjol. i Intensyw. Opieki Medycz.':
            u'Zakład Pielęgniarstwa Anestezjologicznego i Intensywnej Opieki Medycznej',

        u'Zakład Pedagogiki i Dydak. Medycz. z Prac. Umiejęt. Pielęgn.':
            u'Zakład Pedagogiki i Dydaktyki Medycznej z Pracownią Umiejętności Pielęgniarskich',

        u'I Klinika Anestezjol. i Intens. Terapii z Klin. Oddz. Dziec.':
            u'I Klinika Anestezjologii i Intensywnej Terapii z Klinicznym Oddziałem Dziecięcym',

        u'Katedra i Klinika Otolaryn. Dziec., Foniatrii i Audiol.':
            u'Katedra i Klinika Otolaryngologii Dziecięcej, Foniatrii i Audiologii',

        u'Katedra i Klinika Reumatol. i Układow. Chorób Tkanki Łącznej':
            u'Katedra i Klinika Reumatologii i Układowych Chorób Tkanki Łącznej',

        u'I Katedra i Klin. Chirur. Ogóln. i Transplant. i Lecz. Żyw.':
            u'I Katedra i Klinika Chirurgii Ogólnej, Transplantacyjnej i Leczenia Żywieniowego',

        u'II Kated. i Klin. Chir. Ogól. Gastroentero. i Now. Ukł. Pok.':
            u'II Katedra i Klinika Chirurgii Ogólnej, Gastroenterologicznej i Nowotworów Układu Pokarmowego',

        u'Katedra i Zakł.Mikrob. Farmaceut. z Prac. Diagn. Mikrobiol.':
            u'Katedra i Zakład Mikrobiologii Farmaceutycznej z Pracownią Diagnostyki Mikrobiologicznej',

        u'Katedra i Zakład Syntezy i Technologii Chem. Środ. Lecznicz.':
            u'Katedra i Zakład Syntezy i Technologii Chemicznej Środków Leczniczych',

        u'Katedra i Klinika Dermatol., Wenerol. i Dermatol. Dziecięcej':
            u'Katedra i Klinika Dermatologii, Wenerologii i Dermatologii Dziecięcej',

        u'Zakład Rentgenodiagnostyki Stomatolog. i Szczękowo-Twarzowej':
            u'Zakład Rentgenodiagnostyki Stomatologicznej i Szczękowo-Twarzowej',

        u'Katedra i Klinika Chirurgii Szczękowo-Twarzowej':
            u'Klinika Chirurgii Szczękowo-Twarzowej',

        u'Katedra i Zakład Histolog. i Embriol. z Prac. Cytolog. Dośw.':
            u'Katedra i Zakład Histologii i Embriologii z Pracownią Cytologii Doświadczalnej',

        u'Samodzielna Prawcownia Medycyny Jamy Ustnej':
            u'Samodzielna Pracownia Medycyny Jamy Ustnej',

        u'Katedra i Zakł. Prot. Stom. z Prac. Zaburz. Czyn. Narz. Żuc.':
            u'Zakład Protetyki Stomatologicznej',

        u'Klinika Ortopedii i Rehabilitacji':
            u'Klinika Ortopedii i Rehabilitacji Katedry Ortopedii',
        }


