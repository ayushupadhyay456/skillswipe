# SkillSwap

Trade skills, not money. A full-stack Flask platform for peer skill exchange.

## Stack

- **Backend**: Flask, SQLAlchemy (SQLite/Postgres), Flask-Login, Flask-Bcrypt
- **Realtime**: Flask-SocketIO + eventlet
- **Cache**: Redis (notifications, browse cache, unread counts)
- **Frontend**: Vanilla HTML/CSS/JS, Jinja2 templates
- **Font**: Inter + Syne (Google Fonts)

## Project structure

```
skillswap/
├── app.py                  # All routes, models, Redis helpers
├── requirements.txt
├── .env                    # Config (SECRET_KEY, DATABASE_URL, REDIS_URL)
├── templates/
│   ├── base.html           # Nav, toast, SocketIO setup
│   ├── index.html          # Landing page
│   ├── auth.html           # Login + Signup
│   ├── browse.html         # Browse + search + swap modal
│   ├── profile.html        # Public profile + reviews
│   ├── my_profile.html     # Edit your profile
│   ├── swaps.html          # Manage swap requests (sent/received)
│   ├── messages.html       # Conversation list
│   └── chat.html           # Real-time chat
└── static/
    ├── css/main.css
    └── js/main.js
```

## Quick start

```bash
# 1. Clone and enter
cd skillswap

# 2. Create virtualenv
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install deps
pip install -r requirements.txt

# 4. Start Redis (or skip — app runs without Redis, just no caching)
redis-server

# 5. Run
python app.py
```

Visit http://localhost:5000

## Default seed users (password: `password123`)

| Name     | Email                 | Offers  | Wants  |
|----------|-----------------------|---------|--------|
| Priya R. | priya@example.com     | Figma   | Python |
| Arjun K. | arjun@example.com     | Guitar  | React  |
| Sneha M. | sneha@example.com     | French  | Excel  |

## Redis usage

| Key pattern       | What it stores              | TTL   |
|-------------------|-----------------------------|-------|
| `browse:{q}:{cat}`| Browse results JSON         | 60s   |
| `profile:{id}`    | Review list for profile     | 120s  |
| `unread:{id}`     | Unread message count        | 30s   |
| `notifs:{id}`     | Last 20 notifications       | 1hr   |

## Deploying to Render (free tier)

1. Push to GitHub
2. New Web Service → connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `python app.py`
5. Add env vars: `SECRET_KEY`, `DATABASE_URL` (Postgres), `REDIS_URL`
6. Add a free Redis instance from Render

## Next features to build

- [ ] Session scheduling (calendar invite)
- [ ] AI-powered matching ("you know Python, these 3 want Python")  
- [ ] Review system (after swap completion)
- [ ] Category tags (Tech / Music / Language / etc.)
- [ ] Email notifications (Flask-Mail)
