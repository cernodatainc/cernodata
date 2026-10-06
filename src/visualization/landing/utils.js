/**
 * src/visualization/landing/utils.js
 *
 * Text escaping, HTML sanitization, and shared formatting utilities
 * for the cernodata ingestion hub.
 */

/**
 * Escapes unsafe HTML characters to prevent XSS injection in dynamic DOM updates.
 *
 * @param {string|number|null|undefined} str - Raw string or value to escape.
 * @returns {string} Sanitized string safe for HTML rendering.
 */
function escapeHtml(str) {
    return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
