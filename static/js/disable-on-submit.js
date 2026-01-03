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

    // Expose globally so modal dialogs can call it when programmatically submitting forms
    window.disableAllInteractiveElements = function disableAllInteractiveElements() {
        if (isSubmitting) return; // Already disabled
        isSubmitting = true;

        // Disable all buttons
        document.querySelectorAll('button').forEach(btn => {
            btn.disabled = true;
            btn.style.opacity = '0.5';
            btn.style.cursor = 'not-allowed';
        });

        // Make inputs readonly EXCEPT hidden ones (IMPORTANT: readonly still submits values)
        document.querySelectorAll('input').forEach(input => {
            if (input.type !== 'hidden' && input.type !== 'checkbox' && input.type !== 'radio') {
                input.readOnly = true;
                input.style.opacity = '0.5';
                input.style.cursor = 'not-allowed';
            } else if (input.type === 'checkbox' || input.type === 'radio') {
                // For checkboxes and radios, disable pointer events but don't disable them
                input.style.pointerEvents = 'none';
                input.style.opacity = '0.5';
            }
        });

        // Make textareas readonly (IMPORTANT: readonly still submits values)
        document.querySelectorAll('textarea').forEach(textarea => {
            textarea.readOnly = true;
            textarea.style.opacity = '0.5';
            textarea.style.cursor = 'not-allowed';
        });

        // Disable pointer events on selects (can't make selects readonly)
        document.querySelectorAll('select').forEach(select => {
            select.style.pointerEvents = 'none';
            select.style.opacity = '0.5';
            select.style.cursor = 'not-allowed';
        });

        // Disable all links EXCEPT navigation links
        document.querySelectorAll('a').forEach(link => {
            // Keep navigation links active (links inside <nav> tags)
            if (!link.closest('nav')) {
                link.style.pointerEvents = 'none';
                link.style.opacity = '0.6';
            }
        });
    };

    // Intercept all form submissions
    document.addEventListener('submit', function(e) {
        const form = e.target;

        // Skip forms marked with data-no-disable attribute
        if (form.hasAttribute('data-no-disable')) {
            return;
        }

        // Skip forms with class 'no-disable'
        if (form.classList.contains('no-disable')) {
            return;
        }

        window.disableAllInteractiveElements();

        // After 2 seconds, check if we're still on the same page (form validation failed)
        setTimeout(function() {
            if (isSubmitting) {
                // Check if there are error messages on the page
                const hasErrors = document.querySelector('.errorlist, .alert-danger, [style*="color: #e74c3c"], [style*="color:#e74c3c"]');
                if (hasErrors) {
                    console.log('Form validation failed - re-enabling page');
                    window.enableAllInteractiveElements();
                }
            }
        }, 2000);

        // Let the form submit normally
    }, true); // Use capture phase to catch before other handlers

    // Intercept all button clicks (for buttons that don't submit forms)
    document.addEventListener('click', function(e) {
        const target = e.target;

        // Check if clicked element is a button or inside a button
        const button = target.closest('button');

        if (button && button.type !== 'button') {
            // Skip buttons marked with data-no-disable attribute
            if (button.hasAttribute('data-no-disable')) {
                return;
            }

            // Skip buttons with class 'no-disable'
            if (button.classList.contains('no-disable')) {
                return;
            }

            // Skip common cancel/close buttons
            const buttonText = button.textContent.toLowerCase().trim();
            if (buttonText.includes('cancel') || buttonText.includes('close')) {
                return;
            }

            // Only disable for submit buttons or buttons without explicit type="button"
            // Give a tiny delay to let the click handler execute first
            setTimeout(window.disableAllInteractiveElements, 10);
        }
    }, true);

})();
