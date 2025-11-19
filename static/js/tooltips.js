/**
 * Global Tooltip System
 * Automatically initializes tooltips on elements with data-tooltip attribute
 * Works on both hover (desktop) and click/tap (mobile)
 */

(function() {
    'use strict';

    // Track currently active tooltip for mobile
    let currentActiveTooltip = null;

    // Detect if device supports touch
    function isTouchDevice() {
        return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    }

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

        // Handle click/tap - only for mobile/touch devices
        element.addEventListener('click', function(e) {
            // On desktop, hover handles tooltips - clicks should not toggle
            // On mobile/touch, click/tap toggles tooltip
            if (!isTouchDevice()) {
                // Desktop: clicking should close any active tooltip (not toggle)
                if (element.classList.contains('tooltip-active')) {
                    element.classList.remove('tooltip-active');
                    if (currentActiveTooltip === element) {
                        currentActiveTooltip = null;
                    }
                }
                return;
            }

            // Mobile: toggle tooltip
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

        // Position tooltip on hover (for desktop)
        element.addEventListener('mouseenter', function() {
            requestAnimationFrame(() => {
                positionTooltip(element, tooltipContent);
            });
        });
    }

    /**
     * Position tooltip using fixed positioning (escapes overflow:hidden)
     */
    function positionTooltip(element, tooltipContent) {
        const elementRect = element.getBoundingClientRect();
        const tooltipRect = tooltipContent.getBoundingClientRect();

        // Calculate center position
        let left = elementRect.left + (elementRect.width / 2) - (tooltipRect.width / 2);
        let top = elementRect.top - tooltipRect.height - 8; // 8px margin

        // Check if tooltip goes off top of screen
        if (top < 10) {
            // Position below element instead
            top = elementRect.bottom + 8;
            tooltipContent.classList.add('tooltip-bottom');
        } else {
            tooltipContent.classList.remove('tooltip-bottom');
        }

        // Check horizontal bounds
        if (left < 10) {
            left = 10;
        } else if (left + tooltipRect.width > window.innerWidth - 10) {
            left = window.innerWidth - tooltipRect.width - 10;
        }

        // Check vertical bounds (bottom)
        if (top + tooltipRect.height > window.innerHeight - 10) {
            top = window.innerHeight - tooltipRect.height - 10;
        }

        tooltipContent.style.left = left + 'px';
        tooltipContent.style.top = top + 'px';
    }

    /**
     * Check if tooltip goes off-screen and reposition if needed
     */
    function checkTooltipPosition(element, tooltipContent) {
        positionTooltip(element, tooltipContent);
    }

    /**
     * Close active tooltip (used by scroll handler)
     */
    function closeActiveTooltip() {
        if (currentActiveTooltip) {
            currentActiveTooltip.classList.remove('tooltip-active');
            currentActiveTooltip = null;
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

    // Close tooltip on scroll (for mobile)
    let scrollTimeout;
    window.addEventListener('scroll', function() {
        // Debounce scroll events
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(function() {
            closeActiveTooltip();
        }, 50);
    }, { passive: true });

    // Also close on touchmove (for mobile scrolling within elements)
    document.addEventListener('touchmove', function() {
        closeActiveTooltip();
    }, { passive: true });

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
    window.closeActiveTooltip = closeActiveTooltip;
})();
