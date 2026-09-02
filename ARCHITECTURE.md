# Circa architecture

## Application

`app.py` remains the stable WSGI entrypoint and exposes `app` from the `social_app.create_app()` factory. Blueprints separate authentication, users, social relationships, content, messaging, notifications, and media. The same Flask origin serves the API and the Vanilla JavaScript SPA, so CORS is unnecessary.

## Data responsibilities

SQLite stores strongly relational data: users and password hashes, profiles and privacy settings, friendships, blocks, bookmarks, reactions, conversation membership, reports, notification preferences, and upload metadata. Connections enable foreign keys, WAL mode, and a 10-second busy timeout. The service must remain at one replica while SQLite is used.

MongoDB stores flexible/high-volume content: posts, comments, poll votes, private messages, and notifications. Compound indexes cover the feed, profile posts, comments, messages, notifications, hashtags, and poll uniqueness.

Operations that touch both databases validate ownership in SQLite first and write content second. Derived counts are calculated from their authoritative stores rather than accepted from clients. Deletion removes dependent Mongo content only after ownership is verified. Account deletion is a soft-delete: login credentials and public profile identifiers are revoked while content history is preserved under a deleted-account identity.

## API and frontend

New endpoints live under `/api`. Responses use `{ "data": ... }`; errors use `{ "error": { "code": ..., "message": ... } }`. Cursor pagination uses Mongo ObjectIds for feeds, comments, messages, and notifications.

The frontend uses ES modules (`app.js`, `api.js`, and `translations.js`), History API routing, one cookie-aware API wrapper, escaped user text, reusable loading/empty/error states, and Hebrew/English RTL/LTR rendering. Private/authenticated API responses are never cached by the service worker.

## Media

Media bytes are stored in `UPLOAD_DIR` using random UUID filenames. SQLite contains the logical media ID, owner, MIME type, privacy, and conversation association. Images are decoded and rewritten with Pillow to validate content and remove metadata. Video signatures are validated for MP4/WebM. Private attachments are served only after conversation-membership authorization.

## Scalability

The current Railway volume is appropriate for a small single-instance product. PostgreSQL is the natural next relational store, and S3/R2/Cloudinary the natural next media store. The service layer and logical media IDs are designed so those migrations do not require frontend changes.
