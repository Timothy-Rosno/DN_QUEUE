/**
 * Simple Universal Page Blocker
 *
 * When any button is clicked or form is submitted:
 * - Disables ALL interactive elements (buttons, inputs, textareas, selects)
 * - Grays them out visually
 * - Prevents multiple submissions
 *
 * No fancy text changes, no configuration needed - just works.
 */

(function() {
    'use strict';

    let isSubmitting = false;

    function disableAllInteractiveElements() {
        if (isSubmitting) return; // Already disabled
        isSubmitting = true;

        // Disable all buttons
        document.querySelectorAll('button').forEach(btn => {
            btn.disabled = true;
            btn.style.opacity = '0.5';
            btn.style.cursor = 'not-allowed';
        });

        // Disable all inputs
        document.querySelectorAll('input').forEach(input => {
            input.disabled = true;
            input.style.opacity = '0.5';
        });

        // Disable all textareas
        document.querySelectorAll('textarea').forEach(textarea => {
            textarea.disabled = true;
            textarea.style.opacity = '0.5';
        });

        // Disable all selects
        document.querySelectorAll('select').forEach(select => {
            select.disabled = true;
            select.style.opacity = '0.5';
        });

        // Disable all links (optional - prevents navigation during processing)
        document.querySelectorAll('a').forEach(link => {
            link.style.pointerEvents = 'none';
            link.style.opacity = '0.6';
        });
    }

    // Intercept all form submissions
    document.addEventListener('submit', function(e) {
        disableAllInteractiveElements();
        // Let the form submit normally
    }, true); // Use capture phase to catch before other handlers

    // Intercept all button clicks (for buttons that don't submit forms)
    document.addEventListener('click', function(e) {
        const target = e.target;

        // Check if clicked element is a button or inside a button
        const button = target.closest('button');

        if (button && button.type !== 'button') {
            // Only disable for submit buttons or buttons without explicit type="button"
            // Give a tiny delay to let the click handler execute first
            setTimeout(disableAllInteractiveElements, 10);
        }
    }, true);

})();
