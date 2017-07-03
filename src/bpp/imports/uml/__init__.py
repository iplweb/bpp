# -*- encoding: utf-8 -*-


class UML_Egeria_2012_Mangle:
    """Klasa zawierająca informacje, w jaki sposób potraktować nazwy jednostek, ciągi znaków,
    zawarte w importowanym pliku XLS"""

    # Tych jednostek nie importujemy z pliku wejściowego XLS
    ignorowane_jednostki = [
        'Katedra Chemii',
        'Katedra Diagnostyki Laboratoryjnej',
        'Sam. Pracownia Propedeutyki Radiologii Stom. i Szczęk-Twarz',
        'Pracownia Spektrometrii Absorpcji Atomowej',
        'Klinika Endokrynologii i Neurologii Dziecięcej',
        'Pracownia Zarządzania i Ekonomiki Farmaceutycznej',
        'Pracownia Otoneurologiczna',
        'Zakład Elektroradiologii',
        'Pracownia Toksykologii Sądowej',
        'Pracownia Farmakologii Komórkowej i Molekularnej',
        'Pracownia Analizy DNA i Diagnostyki Molekularnej'
        'Samodzielna Pracownia Zdrowia Psychicznego',
        'Zakład Podstaw Pielęgniarstwa i Dydaktyki Medycznej'
    ]

    # W przypadku tych jednostek odpytujemy BEZPOŚREDNIO o nazwę tej jednostki,
    # ponieważ odpytanie standardowe zwróciłoby zbyt dużą ilość jednostek.
    # Ponieważ kliniki mają na początku rzymskie numerki, to icontains
    # znajdzie II katedrę w IIIciej, więc:
    single_fitters = [
        'Zakład Farmakologii',
        'I Katedra i Klinika Ginekologii',
        'II Katedra i Klinika Ginekologii',
        'III Katedra i Klinika Ginekologii',
        ]

    # To zamiany nazw jednostek z tych, które są w XLSie na te, które mamy w BPP
    zamiany_nazw_jednostek = {

        'Katedra i Klinika Ginekologii i Endokrynologii Ginekolog.':
            'Katedra i Klinika Ginekologii i Endokrynologii Ginekologicznej',

        'Zakład Położn., Ginekol. i Pielęg. Położ-Ginekolog.':
            'Zakład Położnictwa, Ginekologii i Pielęgniarstwa Położniczo-Ginekologicznego',

        'Zakład Pielęgniarstwa Anestezjol. i Intensyw. Opieki Medycz.':
            'Zakład Pielęgniarstwa Anestezjologicznego i Intensywnej Opieki Medycznej',

        'Zakład Pedagogiki i Dydak. Medycz. z Prac. Umiejęt. Pielęgn.':
            'Zakład Pedagogiki i Dydaktyki Medycznej z Pracownią Umiejętności Pielęgniarskich',

        'I Klinika Anestezjol. i Intens. Terapii z Klin. Oddz. Dziec.':
            'I Klinika Anestezjologii i Intensywnej Terapii z Klinicznym Oddziałem Dziecięcym',

        'Katedra i Klinika Otolaryn. Dziec., Foniatrii i Audiol.':
            'Katedra i Klinika Otolaryngologii Dziecięcej, Foniatrii i Audiologii',

        'Katedra i Klinika Reumatol. i Układow. Chorób Tkanki Łącznej':
            'Katedra i Klinika Reumatologii i Układowych Chorób Tkanki Łącznej',

        'I Katedra i Klin. Chirur. Ogóln. i Transplant. i Lecz. Żyw.':
            'I Katedra i Klinika Chirurgii Ogólnej, Transplantacyjnej i Leczenia Żywieniowego',

        'II Kated. i Klin. Chir. Ogól. Gastroentero. i Now. Ukł. Pok.':
            'II Katedra i Klinika Chirurgii Ogólnej, Gastroenterologicznej i Nowotworów Układu Pokarmowego',

        'Katedra i Zakł.Mikrob. Farmaceut. z Prac. Diagn. Mikrobiol.':
            'Katedra i Zakład Mikrobiologii Farmaceutycznej z Pracownią Diagnostyki Mikrobiologicznej',

        'Katedra i Zakład Syntezy i Technologii Chem. Środ. Lecznicz.':
            'Katedra i Zakład Syntezy i Technologii Chemicznej Środków Leczniczych',

        'Katedra i Klinika Dermatol., Wenerol. i Dermatol. Dziecięcej':
            'Katedra i Klinika Dermatologii, Wenerologii i Dermatologii Dziecięcej',

        'Zakład Rentgenodiagnostyki Stomatolog. i Szczękowo-Twarzowej':
            'Zakład Rentgenodiagnostyki Stomatologicznej i Szczękowo-Twarzowej',

        'Katedra i Klinika Chirurgii Szczękowo-Twarzowej':
            'Klinika Chirurgii Szczękowo-Twarzowej',

        'Katedra i Zakład Histolog. i Embriol. z Prac. Cytolog. Dośw.':
            'Katedra i Zakład Histologii i Embriologii z Pracownią Cytologii Doświadczalnej',

        'Samodzielna Prawcownia Medycyny Jamy Ustnej':
            'Samodzielna Pracownia Medycyny Jamy Ustnej',

        'Katedra i Zakł. Prot. Stom. z Prac. Zaburz. Czyn. Narz. Żuc.':
            'Zakład Protetyki Stomatologicznej',

        'Klinika Ortopedii i Rehabilitacji':
            'Klinika Ortopedii i Rehabilitacji Katedry Ortopedii',
        }


