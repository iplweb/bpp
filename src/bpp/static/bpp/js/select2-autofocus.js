/**
 * Automatyczne ustawianie fokusa w polu wyszukiwania select2
 * po rozwinięciu kontrolki
 */
(function($) {
    $(document).ready(function() {
        // Nasłuchuj na zdarzenie otwarcia select2
        $(document).on('select2:open', function(e) {
            // Znajdź pole wyszukiwania w rozwiniętym select2 i ustaw na nim focus
            var searchField = document.querySelector(
                '.select2-container--open .select2-search__field'
            );
            if (searchField) {
                searchField.focus();
            }
        });
    });
})(django.jQuery || jQuery);
