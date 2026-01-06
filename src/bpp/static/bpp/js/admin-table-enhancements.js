/**
 * Admin Table Enhancements
 * Adds hover effects and clickable row functionality to Django admin tables
 */

(function($) {
    'use strict';

    /**
     * Makes table rows clickable if they contain exactly one link
     * (excluding action checkboxes)
     */
    function initClickableRows() {
        // Find all tables with id="result_list"
        $('#result_list tbody tr').each(function() {
            var $row = $(this);

            // Find all links in the row, excluding action checkboxes and their containers
            var $links = $row.find('a').filter(function() {
                // Exclude links that are inside action-checkbox containers
                return !$(this).closest('.action-checkbox').length;
            });

            // If exactly one link exists, make the row clickable
            if ($links.length === 1) {
                var $targetLink = $links.first();
                var linkUrl = $targetLink.attr('href');

                // Add clickable-row class for cursor pointer styling
                $row.addClass('clickable-row');

                // Add accessibility attributes
                $row.attr('tabindex', '0');
                $row.attr('role', 'button');

                // Click handler function
                function navigateToLink(e, openInNewTab) {
                    if (openInNewTab) {
                        window.open(linkUrl, '_blank');
                    } else {
                        window.location.href = linkUrl;
                    }
                }

                // Add click handler to the row
                $row.on('click', function(e) {
                    // Don't trigger if clicking directly on:
                    // - a link (let it handle itself)
                    // - an input (checkbox, etc.)
                    // - a button
                    // - a select
                    if ($(e.target).is('a, input, button, select') ||
                        $(e.target).closest('a, input, button, select').length) {
                        return;
                    }

                    // Check if Ctrl/Cmd key is pressed (for opening in new tab)
                    navigateToLink(e, e.ctrlKey || e.metaKey);
                });

                // Add keyboard handler for Enter and Space
                $row.on('keydown', function(e) {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        navigateToLink(e, e.ctrlKey || e.metaKey);
                    }
                });
            }
        });
    }

    // Initialize on document ready
    $(document).ready(function() {
        initClickableRows();
    });

})(grp.jQuery);
