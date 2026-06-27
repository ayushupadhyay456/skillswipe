# SkillSwap

Trade skills, not money. A full-stack Flask platform for peer skill exchange.

## Stack

| Layer | Tech |
|---|---|
| **Backend** | Flask 3.1, SQLAlchemy 2.x, Flask-Login, Flask-Bcrypt, Flask-Migrate |
| **Realtime** | Flask-SocketIO + eventlet |
| **Cache / Pubsub** | Redis 7 |
| **Database** | PostgreSQL 16 (SQLite for local dev without Docker) |
| **Frontend** | Vanilla HTML/CSS/JS, Jinja2 templates, Three.js WebGPU (landing page) |
| **Server** | Gunicorn + eventlet worker |
| **Proxy** | Nginx 1.25 (static files + WebSocket upgrade) |
| **Containers** | Docker + Docker Compose |

## Project structure

```
skillswap/
├── app.py                    # All routes, models, Redis helpers, SocketIO
├── requirements.txt
├── runtime.txt               # Python 3.11.9
├── Dockerfile                # Multi-stage build (base → deps → final)
├── docker-compose.yml        # Production: web + nginx + redis + postgres
├── docker-compose.dev.yml    # Dev overrides (live reload, exposed ports)
├── Makefile                  # Shortcuts: make up, make logs, make shell ...
├── .env.example              # Copy to .env and fill in secrets
├── nginx/
│   └── nginx.conf            # Reverse proxy + WebSocket + static serving
├── templates/
│   ├── base.html             # Nav, toast, SocketIO setup
│   ├── index.html            # Landing page (Three.js voxel scene)
│   ├── auth.html             # Login + Signup
│   ├── browse.html           # Browse + search + swap request modal
│   ├── profile.html          # Public profile + reviews
│   ├── my_profile.html       # Edit your profile
│   ├── swaps.html            # Manage swap requests (sent/received)
│   ├── messages.html         # Conversation list
│   └── chat.html             # Real-time chat
└── static/
    ├── css/main.css
    └── js/main.js
```

## Quick start — Docker (recommended)

```bash
# 1. Copy env config
cp .env.example .env

# 2. Build and start all 4 services (web + nginx + postgres + redis)
docker compose up --build

# App is live at http://localhost (nginx) or http://localhost:5000 (Flask directly)
```

## Quick start — Local dev (no Docker)

```bash
# 1. Create virtualenv
python -m venv venv && source venv/bin/activate

# 2. Install deps
pip install -r requirements.txt

# 3. Start Redis (optional — app degrades gracefully without it)
redis-server &

# 4. Run
python app.py
# → http://localhost:5000
```

## Dev mode with live reload

```bash
# Uses Flask dev server instead of gunicorn — code changes auto-reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

## Makefile shortcuts

```bash
make up          # docker compose up -d (detached)
make up-logs     # docker compose up (with logs)
make down        # stop all services
make build       # rebuild after code changes
make logs        # follow web container logs
make shell       # bash inside web container
make db-shell    # psql inside postgres container
make redis-cli   # redis-cli inside redis container
make clean       # stop + delete volumes (DESTRUCTIVE)
```

## Default seed users (password: `password123`)

| Name | Email | Offers | Wants |
|---|---|---|---|
| Priya R. | priya@example.com | Figma | Python |
| Arjun K. | arjun@example.com | Guitar | React |
| Sneha M. | sneha@example.com | French | Excel |
| Rahul V. | rahul@example.com | Yoga | Video editing |
| Nisha K. | nisha@example.com | SQL | Drawing |
| Dev S.   | dev@example.com   | FastAPI | Tabla |

## Redis cache keys

| Key | What it stores | TTL |
|---|---|---|
| `browse:{q}:{cat}` | Browse results JSON | 60s |
| `profile:{id}` | Review list for profile page | 120s |
| `unread:{id}` | Unread message count | 30s |
| `notifs:{id}` | Last 20 push notifications | 1h |

## Deploying to Render

1. Push to GitHub
2. New Web Service → connect repo
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `gunicorn --worker-class eventlet -w 1 app:app`
5. Add env vars: `SECRET_KEY`, `DATABASE_URL` (Postgres addon), `REDIS_URL` (Redis addon)

> ⚠️ SocketIO requires exactly **1 gunicorn worker**. Multiple workers need a Redis message queue broker — not yet configured.

## Architecture notes

- **`async_mode='eventlet'`** — required for Flask-SocketIO with gunicorn. The Dockerfile CMD and docker-compose both enforce this.
- **Postgres URL fix** — `app.py` rewrites `postgres://` → `postgresql://` automatically (Render/Heroku use the old prefix, SQLAlchemy 2.x requires the new one).
- **`pool_pre_ping=True`** — reconnects dropped DB connections automatically (important in Docker where postgres may restart).
- **Nginx serves `/static/`** directly — no Flask overhead for CSS/JS/images.
- **WebSocket proxy** — nginx.conf includes proper `Upgrade` headers for Socket.IO long-polling + WebSocket transport.

## Next features

- [ ] Session scheduling with calendar invites
- [ ] AI-powered matching (you teach Python → find people who want Python)
- [ ] Review system after swap completion
- [ ] Category tags (Tech / Music / Language / Fitness)
- [ ] Email notifications (Flask-Mail)
- [ ] Flask-Migrate for safe DB schema changes
