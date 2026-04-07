/**
 * owl_timeout_suppress.js
 *
 * PURPOSE: Suppress Owl's "onWillStart timeout" error for large datasets.
 *
 * APPROACH: Use Object.defineProperty with getter to intercept ALL access
 * to console.error, even if code does `const {error} = console`.
 */
(function () {
    'use strict';

    console.log('%c[OWL SUPPRESS] Installing aggressive console.error intercept...', 'color: purple; font-weight: bold;');

    // Save original BEFORE redefining
    var _originalConsoleError = console.error.bind(console);

    function _isOwlTimeout(arg) {
        if (!arg) return false;
        var text = '';
        if (typeof arg === 'string') {
            text = arg;
        } else if (typeof arg.message === 'string') {
            text = arg.message;
        } else {
            try { text = String(arg); } catch (e) { return false; }
        }
        return text.indexOf('onWillStart') !== -1 && text.indexOf('3 seconds') !== -1;
    }

    // Try Object.defineProperty approach
    try {
        var descriptor = Object.getOwnPropertyDescriptor(console, 'error');
        if (descriptor && descriptor.configurable === false) {
            console.warn('[OWL SUPPRESS] console.error is not configurable, using fallback');
            throw new Error('Not configurable');
        }

        Object.defineProperty(console, 'error', {
            get: function() {
                return function() {
                    // Check if Owl timeout
                    var isTimeout = false;
                    for (var i = 0; i < arguments.length; i++) {
                        if (_isOwlTimeout(arguments[i])) {
                            isTimeout = true;
                            break;
                        }
                    }

                    if (isTimeout) {
                        console.log('%c[OWL SUPPRESS] ✅ BLOCKED Owl timeout!', 'color: green; font-weight: bold; font-size: 14px;');
                        return; // Suppress
                    }

                    return _originalConsoleError.apply(console, arguments);
                };
            },
            configurable: true
        });

        console.log('%c[OWL SUPPRESS] ✅ Object.defineProperty installed', 'color: green; font-weight: bold;');
    } catch (e) {
        // Fallback: simple assignment
        console.warn('[OWL SUPPRESS] Falling back to simple assignment', e);
        console.error = function () {
            var isTimeout = false;
            for (var i = 0; i < arguments.length; i++) {
                if (_isOwlTimeout(arguments[i])) {
                    isTimeout = true;
                    break;
                }
            }

            if (isTimeout) {
                console.log('%c[OWL SUPPRESS] ✅ BLOCKED Owl timeout (fallback)!', 'color: green; font-weight: bold;');
                return;
            }

            return _originalConsoleError.apply(console, arguments);
        };
    }

    // Test that our patch works
    console.log('%c[OWL SUPPRESS] Testing patch...', 'color: orange;');
    console.log('Current console.error type:', typeof console.error);
    console.log('%c[OWL SUPPRESS] ✅ Patch ready!', 'color: green; font-weight: bold; font-size: 14px;');
}());
