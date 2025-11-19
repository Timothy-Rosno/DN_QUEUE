/**
 * Global Tooltip System
 * Automatically initializes tooltips on elements with data-tooltip attribute
 * Works on both hover (desktop) and click/tap (mobile)
 */

(function() {
    'use strict';

    // Track currently active tooltip for mobile
    let currentActiveTooltip = null;

    /**
     * Initialize tooltip for an element
     */
    function initTooltip(element) {
        // Skip if already initialized
        if (element.classList.contains('has-tooltip')) {
            return;
        }

        const tooltipText = element.getAttribute('data-tooltip');
        if (!tooltipText) {
            return;
        }

        // Add tooltip class
        element.classList.add('has-tooltip');

        // Create tooltip content element
        const tooltipContent = document.createElement('div');
        tooltipContent.className = 'tooltip-content';
        tooltipContent.textContent = tooltipText;
        element.appendChild(tooltipContent);

        // Handle click/tap for mobile
        element.addEventListener('click', function(e) {
            // Only handle tooltip toggle if this is a tooltip element
            // Don't prevent default or stop propagation - let links/buttons work normally

            // If this tooltip is already active, close it
            if (element.classList.contains('tooltip-active')) {
                element.classList.remove('tooltip-active');
                if (currentActiveTooltip === element) {
                    currentActiveTooltip = null;
                }
            } else {
                // Close any other active tooltip
                if (currentActiveTooltip && currentActiveTooltip !== element) {
                    currentActiveTooltip.classList.remove('tooltip-active');
                }

                // Show this tooltip
                element.classList.add('tooltip-active');
                currentActiveTooltip = element;

                // Position check (prevent going off-screen)
                requestAnimationFrame(() => {
                    checkTooltipPosition(element, tooltipContent);
                });
            }
        });

        // Close tooltip when clicking outside
        document.addEventListener('click', function(e) {
            if (!element.contains(e.target) && element.classList.contains('tooltip-active')) {
                element.classList.remove('tooltip-active');
                if (currentActiveTooltip === element) {
                    currentActiveTooltip = null;
                }
            }
        });
    }

    /**
     * Check if tooltip goes off-screen and reposition if needed
     */
    function checkTooltipPosition(element, tooltipContent) {
        const rect = tooltipContent.getBoundingClientRect();

        // Check if tooltip goes off top of screen
        if (rect.top < 0) {
            tooltipContent.classList.add('tooltip-bottom');
        } else {
            tooltipContent.classList.remove('tooltip-bottom');
        }

        // Check horizontal positioning
        if (rect.left < 0) {
            tooltipContent.style.left = '0';
            tooltipContent.style.transform = 'translateX(0)';
        } else if (rect.right > window.innerWidth) {
            tooltipContent.style.left = 'auto';
            tooltipContent.style.right = '0';
            tooltipContent.style.transform = 'translateX(0)';
        }
    }

    /**
     * Initialize all tooltips on the page
     */
    function initAllTooltips() {
        const elements = document.querySelectorAll('[data-tooltip]');
        elements.forEach(initTooltip);
    }

    /**
     * Initialize tooltips when DOM is ready
     */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAllTooltips);
    } else {
        initAllTooltips();
    }

    /**
     * Watch for dynamically added tooltips
     */
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeType === 1) { // Element node
                    // Check if the node itself has data-tooltip
                    if (node.hasAttribute && node.hasAttribute('data-tooltip')) {
                        initTooltip(node);
                    }
                    // Check descendants
                    if (node.querySelectorAll) {
                        const tooltipElements = node.querySelectorAll('[data-tooltip]');
                        tooltipElements.forEach(initTooltip);
                    }
                }
            });
        });
    });

    // Start observing
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    // Export initialization function for manual use if needed
    window.initTooltip = initTooltip;
    window.initAllTooltips = initAllTooltips;
})();
