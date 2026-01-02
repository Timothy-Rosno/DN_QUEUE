/**
 * FormProtector - Unified utility for preventing duplicate form submissions and button clicks
 *
 * Provides both programmatic and declarative APIs for protecting forms and buttons
 * from duplicate submissions, with customizable loading states and confirmation modals.
 *
 * Usage:
 *
 * 1. Declarative (via data attributes):
 *    <form data-protect data-loading-text="Submitting...">
 *        <button type="submit">Submit</button>
 *    </form>
 *
 * 2. Programmatic:
 *    FormProtector.protect(myForm, { loadingText: 'Processing...' });
 *
 * 3. With confirmation:
 *    <button data-protect
 *            data-confirm="Are you sure?"
 *            data-loading-text="Deleting...">
 *        Delete
 *    </button>
 */
class FormProtector {
    /**
     * Protect a form or button from duplicate submissions
     *
     * @param {HTMLElement} formOrButton - The form or button element to protect
     * @param {Object} options - Configuration options
     * @param {string} options.loadingText - Text to display while processing (default: 'Processing...')
     * @param {boolean} options.disableRelated - Disable all buttons with same class (default: false)
     * @param {string} options.confirmMessage - Show confirmation dialog with this message (default: null)
     * @param {Function} options.onSubmit - Callback to execute on submission (default: null)
     * @param {Function} options.beforeDisable - Callback before disabling (default: null)
     * @param {boolean} options.saveScrollPosition - Save scroll position for restoration after page reload (default: false)
     */
    static protect(formOrButton, options = {}) {
        const {
            loadingText = 'Processing...',
            disableRelated = false,
            confirmMessage = null,
            onSubmit = null,
            beforeDisable = null,
            saveScrollPosition = false
        } = options;

        if (!formOrButton) {
            console.error('FormProtector.protect: No element provided');
            return;
        }

        const element = formOrButton;

        // Prevent double-protection
        if (element.dataset.protected === 'true') {
            return;
        }
        element.dataset.protected = 'true';

        if (element.tagName === 'FORM') {
            console.log(`[FormProtector] Adding submit listener to FORM`);
            element.addEventListener('submit', (e) => {
                console.log(`[FormProtector] Form submit event triggered`);

                // Check if form is already being submitted
                if (element.dataset.submitting === 'true') {
                    console.log(`[FormProtector] Form already submitting, preventing`);
                    e.preventDefault();
                    return;
                }

                // Show confirmation if needed
                if (confirmMessage && !confirm(confirmMessage)) {
                    console.log(`[FormProtector] User cancelled confirmation`);
                    e.preventDefault();
                    return;
                }

                // Execute beforeDisable callback
                if (beforeDisable && beforeDisable(e) === false) {
                    console.log(`[FormProtector] beforeDisable returned false, preventing`);
                    e.preventDefault();
                    return;
                }

                // Save scroll position if needed
                if (saveScrollPosition) {
                    this._saveScrollPosition(element);
                }

                // Mark as submitting
                element.dataset.submitting = 'true';
                console.log(`[FormProtector] Disabling form buttons with text: ${loadingText}`);

                // Disable all submit buttons in the form
                this._disableFormButtons(element, loadingText);

                // Execute onSubmit callback
                if (onSubmit) {
                    onSubmit(e);
                }
            });
        } else if (element.tagName === 'BUTTON' || element.tagName === 'INPUT') {
            element.addEventListener('click', (e) => {
                // Check if already clicked
                if (element.dataset.clicked === 'true') {
                    e.preventDefault();
                    return;
                }

                // Show confirmation if needed
                if (confirmMessage && !confirm(confirmMessage)) {
                    e.preventDefault();
                    return;
                }

                // Execute beforeDisable callback
                if (beforeDisable && beforeDisable(e) === false) {
                    e.preventDefault();
                    return;
                }

                // Save scroll position if needed
                if (saveScrollPosition) {
                    this._saveScrollPosition(element);
                }

                // Mark as clicked
                element.dataset.clicked = 'true';

                // Disable this button
                this._disableButton(element, loadingText);

                // Disable related buttons if requested
                if (disableRelated) {
                    this._disableRelatedButtons(element, loadingText);
                }

                // Execute onSubmit callback
                if (onSubmit) {
                    onSubmit(e);
                }
            });
        } else {
            console.error('FormProtector.protect: Element must be a FORM, BUTTON, or INPUT');
        }
    }

    /**
     * Disable a single button with loading state
     * @private
     */
    static _disableButton(button, text) {
        if (!button || button.disabled) return;

        button.disabled = true;
        button.style.opacity = '0.6';
        button.style.cursor = 'not-allowed';

        // Save original text if not already saved
        if (!button.dataset.originalText) {
            button.dataset.originalText = button.textContent;
        }

        button.textContent = text;
    }

    /**
     * Disable all submit buttons in a form
     * @private
     */
    static _disableFormButtons(form, text) {
        form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(btn => {
            this._disableButton(btn, text);
        });
    }

    /**
     * Disable all buttons with the same class as the clicked button
     * Useful for preventing race conditions when multiple buttons trigger the same action
     * @private
     */
    static _disableRelatedButtons(button, text) {
        // Find class names that look like action classes (e.g., 'undo-check-in-btn', 'check-in-btn')
        const classes = Array.from(button.classList).filter(cls =>
            cls.endsWith('-btn') || cls.includes('action') || cls.includes('submit')
        );

        classes.forEach(className => {
            document.querySelectorAll(`.${className}`).forEach(btn => {
                if (btn !== button) {
                    this._disableButton(btn, text);
                }
            });
        });
    }

    /**
     * Save scroll position to sessionStorage for restoration after page reload
     * @private
     */
    static _saveScrollPosition(element) {
        // Generate a unique key based on the current page
        const pageKey = window.location.pathname.replace(/\//g, '_');
        const scrollKey = `scrollPosition${pageKey}`;
        sessionStorage.setItem(scrollKey, window.scrollY.toString());
    }

    /**
     * Restore scroll position from sessionStorage
     * Should be called on DOMContentLoaded
     */
    static restoreScrollPosition() {
        const pageKey = window.location.pathname.replace(/\//g, '_');
        const scrollKey = `scrollPosition${pageKey}`;
        const savedPosition = sessionStorage.getItem(scrollKey);

        if (savedPosition) {
            window.scrollTo(0, parseInt(savedPosition, 10));
            sessionStorage.removeItem(scrollKey);
        }
    }

    /**
     * Reset a protected form or button (useful for AJAX forms that don't reload)
     * @param {HTMLElement} formOrButton - The element to reset
     */
    static reset(formOrButton) {
        if (!formOrButton) return;

        const element = formOrButton;

        if (element.tagName === 'FORM') {
            element.dataset.submitting = 'false';

            // Re-enable all buttons
            element.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(btn => {
                this._resetButton(btn);
            });
        } else {
            element.dataset.clicked = 'false';
            this._resetButton(element);
        }
    }

    /**
     * Reset a single button to its original state
     * @private
     */
    static _resetButton(button) {
        if (!button) return;

        button.disabled = false;
        button.style.opacity = '';
        button.style.cursor = '';

        if (button.dataset.originalText) {
            button.textContent = button.dataset.originalText;
        }
    }
}

/**
 * Auto-initialize FormProtector for elements with data-protect attribute
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('[FormProtector] Initializing...');

    // Protect all elements with data-protect attribute
    const protectedElements = document.querySelectorAll('[data-protect]');
    console.log(`[FormProtector] Found ${protectedElements.length} elements with data-protect attribute`);

    protectedElements.forEach(element => {
        const options = {
            loadingText: element.dataset.loadingText || 'Processing...',
            disableRelated: element.dataset.disableRelated === 'true',
            confirmMessage: element.dataset.confirm || null,
            saveScrollPosition: element.dataset.saveScroll === 'true'
        };

        console.log(`[FormProtector] Protecting ${element.tagName}#${element.id || 'no-id'}`, options);
        FormProtector.protect(element, options);
    });

    // Restore scroll position if saved
    FormProtector.restoreScrollPosition();

    console.log('[FormProtector] Initialization complete');
});

// Make FormProtector globally available
window.FormProtector = FormProtector;
