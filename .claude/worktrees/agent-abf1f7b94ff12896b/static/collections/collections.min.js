/*
 * collections.min.js — minimal List polyfill
 * Provides the List class used by general_notifications.html and chat_notifications.html.
 * List wraps a plain JavaScript Array, exposing all native Array methods
 * (.filter, .push, .length, .forEach, .find, etc.).
 *
 * Usage:  var list = new List([]);   // identical to []
 *         list.push(item);
 *         var results = list.filter(fn);
 *         list.length;
 */
(function (root) {
    "use strict";

    /**
     * List constructor.
     * Returns a plain Array (not `this`), so all Array prototype methods
     * are available without any special sub-classing.
     *
     * @param {Array} [arr] - optional initial items
     * @returns {Array}
     */
    function List(arr) {
        return arr ? Array.prototype.slice.call(arr) : [];
    }

    root.List = List;

}(typeof window !== "undefined" ? window : this));
