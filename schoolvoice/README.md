# SchoolVoice — Anonymous Suggestion Box

A small Flask website: students pin anonymous notes on a "board," staff review
them from a password-protected dashboard. Light/dark mode, animated form,
"note-drop" submit animation.

## Run it locally

You need Python 3.9+ installed.

```bash
cd schoolvoice
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5000** in your browser.

- Public form: `http://localhost:5000/`
- Staff dashboard: `http://localhost:5000/admin`
  - Default login (first run only): username `admin`, password `changeme123`

**Change the default password immediately after your first login** — no
terminal needed. Once logged in:
- **Change password**: top of the dashboard → updates your own login
- **Manage staff**: top of the dashboard → add new staff logins (e.g. one
  per teacher/counselor) or remove old ones, all from the browser

Staff accounts are stored in the site's own database (`suggestions.db`), not
in environment variables — so any staff member with a login can rotate their
own password whenever they need to, without touching code or a server.

**Two access levels:**
- **Admin** — can view/triage notes, change their own password, *and* add or
  remove staff accounts (the "Manage staff" page)
- **Staff** — can view/triage notes and change their own password only. They
  cannot see the "Manage staff" page, and the server rejects any attempt to
  reach it directly, even with a crafted request.

The very first account (`admin` / `changeme123`) is admin-level. When
creating new accounts from "Manage staff," you choose which level each
person gets. There must always be at least one admin account and at least
one account overall — the app won't let the last one be deleted, so nobody
can accidentally lock everyone out.

It's still worth setting a strong `SECRET_KEY` environment variable before
deploying (this only protects login sessions, not passwords):

```bash
export SECRET_KEY="some-long-random-string"
python app.py
```

## How anonymity is protected

- No names, emails, logins, or accounts for students — anyone can submit without identifying themselves.
- IP addresses are **never stored directly**. They're one-way hashed (like a
  fingerprint you can't reverse) and only used briefly to stop spam floods
  (max 3 submissions/hour from the same connection), then automatically
  discarded after the hour passes.
- Admins only ever see: category, message text, and timestamp. Nothing else.

## Spam/joke-submission safeguards already built in

- Minimum message length (20 characters)
- A "genuine concern" honesty checkbox required before sending
- Rate limiting per connection (3 submissions/hour)
- A light keyword filter that auto-flags likely joke/abusive submissions for
  staff to review first (doesn't block them, just marks them)
- All submissions go to a review queue — nothing is "public," so joke posts
  have no audience

## Deploying so the whole school can use it

Right now this only runs on your own computer. To make it a real website
your school can visit from any device, you need to host it somewhere.

### Option A: Docker (recommended if your host supports it)

This project now includes a `Dockerfile` and `docker-compose.yml`. Docker
packages the app, Python, and all dependencies into one portable container —
useful if you outgrow PythonAnywhere and want to deploy to a VPS, Railway,
Fly.io, or any Docker-friendly host.

```bash
docker compose up --build
```

Then open **http://localhost:5000**. The database is stored in a Docker
volume (`schoolvoice-data`) — it survives container rebuilds, so redeploying
never wipes your notes or staff accounts.

Before deploying for real, edit `docker-compose.yml` and change:
```yaml
- SECRET_KEY=change-this-to-a-long-random-string
```
to an actual random string — this protects staff login sessions.

**Without Docker Compose**, plain Docker commands work too:
```bash
docker build -t schoolvoice .
docker run -p 5000:5000 -v schoolvoice-data:/app/data -e SECRET_KEY=your-secret schoolvoice
```

### Option B: PythonAnywhere (easiest, no Docker needed)

Good free/cheap options for a first deploy:

- **PythonAnywhere** (easiest for beginners, free tier available, no Docker needed)
- **Render** (free tier, auto-deploys from GitHub, supports Docker)
- **Railway** (supports Docker, persistent volumes on paid tier)

All three have simple guides for deploying a Flask app — happy to walk you
through whichever one you pick.

## Project structure

```
schoolvoice/
├── app.py                  # Flask backend (routes, database, auth)
├── requirements.txt
├── Dockerfile               # container build instructions
├── docker-compose.yml       # local Docker run config with persistent volume
├── .dockerignore
├── suggestions.db          # created automatically on first run (SQLite)
├── templates/
│   ├── index.html          # public form
│   ├── admin_login.html
│   └── admin_dashboard.html
└── static/
    ├── css/
    │   ├── style.css       # design system (colors, type, light/dark)
    │   ├── board.css        # public form + note-drop animation
    │   └── admin.css       # login + dashboard
    └── js/
        ├── theme.js        # dark mode toggle + scroll reveal
        ├── main.js         # form logic + submit animation
        └── admin.js        # dashboard status updates
```

## Next features worth adding

- Email/SMS alert to staff when a "Bullying / Safety" note comes in
- Export notes to CSV for record-keeping
- Multiple admin accounts with roles
