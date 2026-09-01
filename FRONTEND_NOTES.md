# Frontend notes

## Run and open

1. Start MongoDB locally (the existing backend expects `mongodb://localhost:27017`).
2. From the project directory run:

   ```bash
   python app.py
   ```

3. Open <http://127.0.0.1:5000/>.

## Files created

- `static/index.html`
- `static/css/app.css`
- `static/js/app.js`
- `FRONTEND_NOTES.md`

## Existing endpoints used

- `POST /signup`
- `POST /login`
- `GET /users`
- `GET /posts/<user_id>`
- `GET /my/requests` with the existing user-ID header contract
- `PUT /my/requests/<follower_id>/<approve|reject>`
- `POST /friend-request/<follower_id>/<followed_id>`
- `POST /my/post/add`, `/my/post/delete`, and `/my/post/comment` with the existing user-ID header contract

## Existing backend limitations

- Browsers/Werkzeug discard HTTP header names containing underscores. The frontend sends the standard transport spelling `User-Id`; Flask's case-insensitive header lookup in `app.py` (`request.headers.get("user_id")`) resolves it correctly.
- Approve and reject are supported by the existing `PUT /my/requests/...` route and are wired into the requests view.
- The feed includes the current user's ID as well as approved friends, so a newly created own post appears after refresh.
- `seed_data.py` is destructive development-only sample data. It now matches the current friendship schema but must never run automatically in deployment.
- Authentication is the project's existing username/password and `user_id`-header model. The frontend never stores the password, but this model should not be considered production-secure.

Railway and Atlas setup is documented in `DEPLOYMENT.md`. The MongoDB document structure and SQLite schema were not changed.
