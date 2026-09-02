# Circa frontend

The frontend is a same-origin, installable Vanilla JavaScript SPA.

- `static/index.html` contains the semantic application shell and local SVG icon sprite.
- `static/css/app.css` contains the responsive RTL/LTR light/dark design system.
- `static/js/api.js` is the only API transport and automatically sends session cookies and CSRF tokens.
- `static/js/translations.js` contains all Hebrew and English UI copy.
- `static/js/app.js` provides routing, state, rendering, uploads, feeds, profiles, social actions, messaging, notifications, search, and settings.
- `static/manifest.webmanifest` and `static/service-worker.js` provide an installable shell. The service worker caches only versioned public static assets and never `/api` responses.

Authentication identity is never stored in localStorage. Only language and appearance preferences are persisted there. All user-provided text is escaped before any HTML rendering; mentions and hashtags are converted to controlled internal buttons after tokenization.

Supported deep links include `/home/global`, `/home/friends`, `/explore`, `/search`, `/people`, `/requests`, `/messages/<id>`, `/u/<username>`, `/notifications`, `/bookmarks`, and `/settings/<section>`.
