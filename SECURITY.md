# Security model

## Authentication

Identity comes only from Flask's cryptographically signed session cookie. The cookie is `HttpOnly`, `SameSite=Lax`, and `Secure` in production. Client-provided user-ID headers are not accepted. `/api/me` is the only session bootstrap source for the frontend.

Passwords use Werkzeug's modern password hashing. Migration 2 hashes every legacy plaintext password in place without logging it and clears the legacy `password` column. New signup and password changes always store hashes. Password change and soft account deletion require the current password.

## Request protection

Every state-changing `/api` request requires a session-bound CSRF token sent in `X-CSRF-Token`. Login/signup receive a pre-authentication token from `/api/csrf`. Authentication, content creation, messages, uploads, search, and relationship actions are rate-limited.

Security headers include a same-origin Content Security Policy, `frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, strict referrer behavior, a restrictive Permissions Policy, and COOP. The project has no broad CORS policy and no inline JavaScript.

## Authorization

All post/comment/profile/message/media operations derive the actor from the session and verify ownership or membership on the server. Feed and profile queries enforce visibility, accepted friendship state, and bidirectional blocking. Private attachment delivery verifies conversation membership for every request.

## Upload safety

Raw filenames are never used for storage. Images must decode as JPEG, PNG, WebP, or GIF and are rewritten. SVG and arbitrary files are rejected. MP4/WebM signatures are checked, sizes are capped, and paths are generated UUIDs within the configured upload directory.

## Operational notes

`SECRET_KEY`, `MONGO_URI`, and production paths remain Railway variables and are never committed. SQLite is backed up to `/data/backups/app-pre-circa-v2.db` before the first v2 migration. Migrations are idempotent and recorded in `schema_migrations`. API errors never return raw database exceptions.
