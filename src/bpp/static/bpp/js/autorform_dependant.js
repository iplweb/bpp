(function ($) {
    // FD#640: w formularzu zgłaszania prac pole „Dyscyplina naukowa” jest
    // oznaczone ``data-tylko-autor-uczelni`` — dla autora spoza uczelni
    // chowamy je (i czyścimy wartość). W pozostałych formularzach (admin)
    // pola nie mają tego atrybutu, więc nic się tam nie zmienia.
    var poleDyscypliny = function (prefix) {
        return $(':input[name=' + prefix + 'dyscyplina_naukowa]');
    };

    var tylkoDlaAutorowUczelni = function (prefix) {
        return poleDyscypliny(prefix).is('[data-tylko-autor-uczelni]');
    };

    var pokazDyscypline = function (prefix, pokaz) {
        var pole = poleDyscypliny(prefix);
        var holder = pole.closest('.holder');
        if (pokaz) {
            holder.show();
        } else {
            pole.val(null).trigger('change');
            holder.hide();
        }
    };

    // FD#640: pole „Jednostka” w formularzu zgłaszania prac jest oznaczone
    // ``data-obcy-tylko-obca-jednostka`` — autorowi spoza uczelni ustawiamy
    // jednostkę obcą uczelni (API zwraca ją w ``obca_jednostka_*``, gdy jest
    // skonfigurowana). Autocomplete tego pola i tak podpowiada takiemu
    // autorowi tylko ją, a serwer odrzuca każdą inną jednostkę.
    var poleJednostki = function (prefix) {
        return $(':input[name=' + prefix + 'jednostka]');
    };

    var obcyTylkoObcaJednostka = function (prefix) {
        return poleJednostki(prefix).is('[data-obcy-tylko-obca-jednostka]');
    };

    // FD#640: jednostka obca nigdy nie afiliuje. Po wybraniu jednostki, która
    // nie przyjmuje afiliacji (autocomplete i API podają
    // ``przyjmuje_afiliacje``), odznaczamy „Afiliuje”; gdy potem wybrano
    // jednostkę przyjmującą afiliację, zaznaczamy je z powrotem — ale tylko,
    // jeśli to my je odznaczyliśmy (nie nadpisujemy decyzji użytkownika).
    var poleAfiliuje = function (prefix) {
        return $(':input[name=' + prefix + 'afiliuje]').filter('[type=checkbox]');
    };

    var ustawAfiliacje = function (prefix, przyjmuje) {
        var pole = poleAfiliuje(prefix);
        if (!pole.length)
            return;
        if (przyjmuje === false) {
            if (pole.prop('checked'))
                pole.prop('checked', false)
                    .data('bpp-odznaczone-automatycznie', true)
                    .trigger('change');
        } else if (przyjmuje === true && pole.data('bpp-odznaczone-automatycznie')) {
            pole.prop('checked', true)
                .removeData('bpp-odznaczone-automatycznie')
                .trigger('change');
        }
    };

    var ustawJednostke = function (prefix, id, nazwa, przyjmujeAfiliacje) {
        var pole = poleJednostki(prefix);
        pole.find('option').filter(function () {
            return this.value === String(id);
        }).remove();
        pole.append($('<option>', {value: id, text: nazwa, selected: true}));
        pole.trigger('change');
        ustawAfiliacje(prefix, przyjmujeAfiliacje);
    };

    var obcaJednostkaDlaObcego = function (prefix, data) {
        if (!obcyTylkoObcaJednostka(prefix) || data.autor_uczelni !== false)
            return null;
        if (!data.obca_jednostka_id)
            return null;
        return {id: data.obca_jednostka_id, nazwa: data.obca_jednostka_nazwa};
    };

    // FD#640: ostatnie żądanie wygrywa. Odpowiedź na wcześniejsze żądanie
    // (np. po zmianie autora A → B → A) jest ignorowana, a pola, które
    // użytkownik zmienił po wysłaniu żądania, nie są nadpisywane.
    var licznikZadan = {};

    var noweZadanie = function (prefix) {
        licznikZadan[prefix] = (licznikZadan[prefix] || 0) + 1;
        return {
            nr: licznikZadan[prefix],
            jednostka: poleJednostki(prefix).val(),
            dyscyplina: poleDyscypliny(prefix).val()
        };
    };

    var zadanieAktualne = function (prefix, zadanie) {
        return licznikZadan[prefix] === zadanie.nr;
    };

    var jednostkaNieruszona = function (prefix, zadanie) {
        return poleJednostki(prefix).val() === zadanie.jednostka;
    };

    var dyscyplinaNieruszona = function (prefix, zadanie) {
        return poleDyscypliny(prefix).val() === zadanie.dyscyplina;
    };

    var zapytajOAutora = function (element) {
        // CSRF token z najbliższego formularza — nie polegamy na
        // globalnym $.ajaxSetup, bo public-facing zglos_publikacje
        // nie ma go w base.html (tylko admin/base.html).
        var csrfToken = $(element).closest('form').find(
            '[name=csrfmiddlewaretoken]'
        ).val();
        return $.ajax({
            url: "/bpp/api/ostatnia-jednostka-i-dyscyplina/",
            context: document.body,
            method: "POST",
            data: {
                'autor_id': $(element).val(),
                'rok': $("#id_rok").val(),
                'csrfmiddlewaretoken': csrfToken
            }
        });
    };

    var autorform_dependant = function () {
        var prefix = $(this).getFormPrefix();
        var value = $(this).val();

        if (!value) {
            noweZadanie(prefix);  // unieważnia odpowiedzi w drodze
            $(':input[name=' + prefix + 'jednostka]').val(null).trigger('change');
            $(':input[name=' + prefix + 'typ_odpowiedzialnosci]').val(null).trigger('change');
            $(':input[name=' + prefix + 'zapisany_jako]').val(null).trigger('change');
            $(':input[name=' + prefix + 'dyscyplina_naukowa]').val(null).trigger('change');
            if (tylkoDlaAutorowUczelni(prefix))
                pokazDyscypline(prefix, true);
        } else {
            var zadanie = noweZadanie(prefix);
            zapytajOAutora(this).done(function (data) {
                if (data.status == 'error' || !zadanieAktualne(prefix, zadanie))
                    return;

                if (jednostkaNieruszona(prefix, zadanie)) {
                    var obca = obcaJednostkaDlaObcego(prefix, data);
                    if (obca) {
                        ustawJednostke(prefix, obca.id, obca.nazwa, false);
                    } else if (data.jednostka_id && data.nazwa) {
                        ustawJednostke(
                            prefix, data.jednostka_id, data.nazwa,
                            data.jednostka_przyjmuje_afiliacje
                        );
                    }
                }

                var spozaUczelni = (
                    tylkoDlaAutorowUczelni(prefix) && data.autor_uczelni === false
                );
                if (tylkoDlaAutorowUczelni(prefix))
                    pokazDyscypline(prefix, !spozaUczelni);

                // FD#640: dyscyplina poprzedniego autora nie może zostać przy
                // nowym (np. autor B ma dwie dyscypliny w roku i API nie
                // podaje żadnej). Jeśli użytkownik nie ruszał pola od zmiany
                // autora, czyścimy je, a potem ewentualnie wpisujemy
                // podpowiedź dla nowego autora.
                if (dyscyplinaNieruszona(prefix, zadanie)) {
                    var pole = poleDyscypliny(prefix);
                    if (data['dyscyplina_id'] && !spozaUczelni) {
                        pole.find('option').filter(function () {
                            return this.value === String(data['dyscyplina_id']);
                        }).remove();
                        pole.append($('<option>', {
                            value: data['dyscyplina_id'],
                            text: data['dyscyplina_nazwa'],
                            selected: true
                        }));
                        pole.val(String(data['dyscyplina_id'])).trigger('change');
                    } else if (pole.val()) {
                        pole.val(null).trigger('change');
                    }
                }

                $(':input[name=' + prefix + 'zapisany_jako]').val(null).trigger('change');

            });

        }
    };

    // FD#640: formularz wyrenderowany z już wybranym autorem (powrót do kroku,
    // błąd walidacji, edycja zwróconego zgłoszenia) — ustawiamy widoczność
    // pola dyscypliny, a jednostkę zmieniamy tylko autorowi spoza uczelni
    // (na obcą); autorowi uczelni wybranej jednostki nie nadpisujemy.
    var sprawdzWybranegoAutora = function (element) {
        var prefix = $(element).getFormPrefix();
        if (!$(element).val())
            return;
        if (!tylkoDlaAutorowUczelni(prefix) && !obcyTylkoObcaJednostka(prefix))
            return;
        var zadanie = noweZadanie(prefix);
        zapytajOAutora(element).done(function (data) {
            if (data.status == 'error' || !zadanieAktualne(prefix, zadanie))
                return;
            if (tylkoDlaAutorowUczelni(prefix))
                pokazDyscypline(prefix, data.autor_uczelni !== false);
            var obca = obcaJednostkaDlaObcego(prefix, data);
            if (obca && jednostkaNieruszona(prefix, zadanie)
                && poleJednostki(prefix).val() !== String(obca.id))
                ustawJednostke(prefix, obca.id, obca.nazwa, false);
        });
    };

    $(document).on('autocompleteLightInitialize', '[data-autocomplete-light-function=select2]', function () {
        $(':input[name$=autor]').off('change', autorform_dependant);
        $(':input[name$=autor]').on('change', autorform_dependant);
        if (/(^|-)autor$/.test($(this).attr('name') || ''))
            sprawdzWybranegoAutora(this);
    });

    // FD#640: ręczny wybór jednostki z listy — wynik autocomplete niesie
    // ``przyjmuje_afiliacje``.
    $(document).on('select2:select', ':input[name$=jednostka]', function (e) {
        var dane = e.params && e.params.data;
        if (dane && typeof dane.przyjmuje_afiliacje === 'boolean')
            ustawAfiliacje($(this).getFormPrefix(), dane.przyjmuje_afiliacje);
    });

    // Ręczna zmiana „Afiliuje” przez użytkownika — od teraz to jego decyzja.
    $(document).on('change', ':input[name$=afiliuje]', function (e) {
        if (!e.isTrigger)
            $(this).removeData('bpp-odznaczone-automatycznie');
    });
}(django.jQuery || jQuery));
