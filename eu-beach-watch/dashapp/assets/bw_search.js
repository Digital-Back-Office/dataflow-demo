// EU Beach Watch — search box behaviour.
//
// The Dash server callback for search results is fed by a debounced value:
// every keystroke resets a 2s timer, and only when the user stops typing does
// the final value get pushed into the `search-debounce` store. While the
// timer is pending, a "Searching…" indicator (pre-rendered in the layout as
// #search-loading) is shown in the dropdown area.

window.dash_clientside = Object.assign({}, window.dash_clientside, {
    bwsearch: {
        debounce: function (value) {
            if (window.__bwSearchTimer) {
                clearTimeout(window.__bwSearchTimer);
            }
            if (!value || value.trim().length < 2) {
                return Promise.resolve('');
            }
            return new Promise(function (resolve) {
                window.__bwSearchTimer = setTimeout(function () {
                    resolve(value);
                }, 2000);
            });
        },

        loadingIndicator: function (value) {
            var visible = value && value.trim().length >= 2;
            return {display: visible ? 'block' : 'none'};
        },
    }
});
