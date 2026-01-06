// Polish language for Select2 - registered in Select2's AMD system
// This prevents the "language file could not be loaded" warning and delay

var charsWords = ['znak', 'znaki', 'znaków'];
var itemsWords = ['element', 'elementy', 'elementów'];

function pluralWord(n, words) {
    if (n === 1) return words[0];
    if (n > 1 && n <= 4) return words[1];
    if (n >= 5) return words[2];
}

var plLanguage = {
    errorLoading: function() { return 'Nie można załadować wyników.'; },
    inputTooLong: function(args) {
        var over = args.input.length - args.maximum;
        return 'Usuń ' + over + ' ' + pluralWord(over, charsWords);
    },
    inputTooShort: function(args) {
        var remaining = args.minimum - args.input.length;
        return 'Podaj przynajmniej ' + remaining + ' ' + pluralWord(remaining, charsWords);
    },
    loadingMore: function() { return 'Trwa ładowanie…'; },
    maximumSelected: function(args) {
        return 'Możesz zaznaczyć tylko ' + args.maximum + ' ' +
            pluralWord(args.maximum, itemsWords);
    },
    noResults: function() { return 'Brak wyników'; },
    searching: function() { return 'Trwa wyszukiwanie…'; },
    removeAllItems: function() { return 'Usuń wszystkie przedmioty'; }
};

// Register Polish language in Select2's internal AMD system
// This prevents dynamic loading attempts and associated delays
if (window.jQuery && window.jQuery.fn.select2 && window.jQuery.fn.select2.amd) {
    window.jQuery.fn.select2.amd.define('select2/i18n/pl', [], function() {
        return plLanguage;
    });
}

// Also export to window for fallback/default setting
window.select2PlLanguage = plLanguage;
