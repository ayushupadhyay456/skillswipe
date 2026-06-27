from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask_socketio import SocketIO, emit, join_room
from datetime import datetime
import redis
import json
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///skillswap.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
login_manager = LoginManager(app)
login_manager.login_view = 'login'

try:
    r = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'), decode_responses=True)
    r.ping()
    redis_ok = True
except:
    r = None
    redis_ok = False

# ─── Models ───────────────────────────────────────────────────────────────────

from flask_login import UserMixin

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    city = db.Column(db.String(100))
    bio = db.Column(db.Text)
    avatar_initials = db.Column(db.String(3))
    avatar_color = db.Column(db.String(20), default='teal')
    offer_skill = db.Column(db.String(100))
    want_skill = db.Column(db.String(100))
    rating = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)
    sessions_done = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sent_requests = db.relationship('SwapRequest', foreign_keys='SwapRequest.sender_id', backref='sender', lazy=True)
    received_requests = db.relationship('SwapRequest', foreign_keys='SwapRequest.receiver_id', backref='receiver', lazy=True)

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'city': self.city or '',
            'bio': self.bio or '',
            'avatar_initials': self.avatar_initials or self.name[:2].upper(),
            'avatar_color': self.avatar_color,
            'offer_skill': self.offer_skill or '',
            'want_skill': self.want_skill or '',
            'rating': round(self.rating, 1),
            'review_count': self.review_count,
            'sessions_done': self.sessions_done,
        }


class SwapRequest(db.Model):
    __tablename__ = 'swap_requests'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, declined
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sender = db.relationship('User', foreign_keys=[sender_id])


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewed_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewer = db.relationship('User', foreign_keys=[reviewer_id])


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ─── Redis Helpers ─────────────────────────────────────────────────────────────

def cache_set(key, data, ttl=300):
    if r:
        r.setex(key, ttl, json.dumps(data))

def cache_get(key):
    if r:
        val = r.get(key)
        if val:
            return json.loads(val)
    return None

def cache_del(key):
    if r:
        r.delete(key)

def get_unread_count(user_id):
    key = f'unread:{user_id}'
    cached = cache_get(key)
    if cached is not None:
        return cached
    count = Message.query.filter_by(receiver_id=user_id, read=False).count()
    cache_set(key, count, ttl=30)
    return count

def notify_user(user_id, notif_type, text):
    notif = {'type': notif_type, 'text': text, 'ts': datetime.utcnow().isoformat()}
    key = f'notifs:{user_id}'
    existing = cache_get(key) or []
    existing.insert(0, notif)
    cache_set(key, existing[:20], ttl=3600)
    socketio.emit('notification', notif, room=f'user_{user_id}')


# ─── Auth Routes ───────────────────────────────────────────────────────────────

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('browse'))
    if request.method == 'POST':
        data = request.form
        if User.query.filter_by(email=data['email']).first():
            flash('Email already registered.', 'error')
            return render_template('auth.html', page='signup')
        colors = ['teal','purple','coral','amber','blue','pink']
        import random
        user = User(
            name=data['name'],
            email=data['email'],
            city=data.get('city', ''),
            offer_skill=data.get('offer_skill', ''),
            want_skill=data.get('want_skill', ''),
            avatar_initials=data['name'][:2].upper(),
            avatar_color=random.choice(colors),
        )
        user.set_password(data['password'])
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('browse'))
    return render_template('auth.html', page='signup')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('browse'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('browse'))
        flash('Invalid email or password.', 'error')
    return render_template('auth.html', page='login')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# ─── Main Routes ───────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('browse'))
    total_users = User.query.count()
    total_swaps = SwapRequest.query.filter_by(status='accepted').count()
    return render_template('index.html', total_users=total_users, total_swaps=total_swaps)


@app.route('/browse')
def browse():
    q = request.args.get('q', '').strip()
    category = request.args.get('cat', '')

    cache_key = f'browse:{q}:{category}'
    cached = cache_get(cache_key)

    if not cached:
        query = User.query
        if current_user.is_authenticated:
            query = query.filter(User.id != current_user.id)
        if q:
            query = query.filter(
                db.or_(
                    User.offer_skill.ilike(f'%{q}%'),
                    User.want_skill.ilike(f'%{q}%'),
                    User.name.ilike(f'%{q}%'),
                )
            )
        users = query.order_by(User.rating.desc(), User.created_at.desc()).limit(30).all()
        cached = [u.to_dict() for u in users]
        cache_set(cache_key, cached, ttl=60)

    total_users = User.query.count()
    total_swaps = SwapRequest.query.filter_by(status='accepted').count()
    unread = get_unread_count(current_user.id) if current_user.is_authenticated else 0

    return render_template('browse.html',
        users=cached, q=q, category=category,
        total_users=total_users, total_swaps=total_swaps, unread=unread)


@app.route('/profile/<int:user_id>')
def profile(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return redirect(url_for('browse'))

    cache_key = f'profile:{user_id}'
    cached_reviews = cache_get(cache_key)
    if not cached_reviews:
        reviews = Review.query.filter_by(reviewed_id=user_id).order_by(Review.created_at.desc()).limit(10).all()
        cached_reviews = [{
            'reviewer_name': rv.reviewer.name,
            'reviewer_initials': rv.reviewer.avatar_initials or rv.reviewer.name[:2].upper(),
            'reviewer_color': rv.reviewer.avatar_color,
            'rating': rv.rating,
            'comment': rv.comment,
            'date': rv.created_at.strftime('%b %Y'),
        } for rv in reviews]
        cache_set(cache_key, cached_reviews, ttl=120)

    swap_status = None
    if current_user.is_authenticated and current_user.id != user_id:
        req = SwapRequest.query.filter(
            db.or_(
                db.and_(SwapRequest.sender_id == current_user.id, SwapRequest.receiver_id == user_id),
                db.and_(SwapRequest.sender_id == user_id, SwapRequest.receiver_id == current_user.id),
            )
        ).order_by(SwapRequest.created_at.desc()).first()
        if req:
            swap_status = req.status

    unread = get_unread_count(current_user.id) if current_user.is_authenticated else 0
    return render_template('profile.html', user=user, reviews=cached_reviews, swap_status=swap_status, unread=unread)


@app.route('/my-profile', methods=['GET', 'POST'])
@login_required
def my_profile():
    if request.method == 'POST':
        current_user.name = request.form.get('name', current_user.name)
        current_user.city = request.form.get('city', '')
        current_user.bio = request.form.get('bio', '')
        current_user.offer_skill = request.form.get('offer_skill', '')
        current_user.want_skill = request.form.get('want_skill', '')
        current_user.avatar_initials = current_user.name[:2].upper()
        db.session.commit()
        cache_del(f'profile:{current_user.id}')
        flash('Profile updated.', 'success')
        return redirect(url_for('my_profile'))
    unread = get_unread_count(current_user.id)
    return render_template('my_profile.html', user=current_user, unread=unread)


# ─── Swap Request Routes ───────────────────────────────────────────────────────

@app.route('/swap/request/<int:receiver_id>', methods=['POST'])
@login_required
def send_swap_request(receiver_id):
    if receiver_id == current_user.id:
        return jsonify({'error': 'Cannot request yourself'}), 400

    existing = SwapRequest.query.filter_by(
        sender_id=current_user.id, receiver_id=receiver_id, status='pending'
    ).first()
    if existing:
        return jsonify({'error': 'Request already sent'}), 400

    message = request.json.get('message', '')
    req = SwapRequest(sender_id=current_user.id, receiver_id=receiver_id, message=message)
    db.session.add(req)
    db.session.commit()

    receiver = db.session.get(User, receiver_id)
    notify_user(receiver_id, 'swap_request',
        f'{current_user.name} wants to swap {current_user.offer_skill} ↔ {current_user.want_skill}')

    return jsonify({'status': 'sent', 'request_id': req.id})


@app.route('/swap/<int:req_id>/respond', methods=['POST'])
@login_required
def respond_swap(req_id):
    req = db.session.get(SwapRequest, req_id)
    if not req or req.receiver_id != current_user.id:
        return jsonify({'error': 'Not found'}), 404

    action = request.json.get('action')
    if action == 'accept':
        req.status = 'accepted'
        req.sender.sessions_done += 1
        current_user.sessions_done += 1
        notify_user(req.sender_id, 'swap_accepted',
            f'{current_user.name} accepted your swap request!')
    elif action == 'decline':
        req.status = 'declined'
        notify_user(req.sender_id, 'swap_declined',
            f'{current_user.name} declined your swap request.')

    db.session.commit()
    return jsonify({'status': req.status})


@app.route('/swaps')
@login_required
def swaps():
    sent = SwapRequest.query.filter_by(sender_id=current_user.id).order_by(SwapRequest.created_at.desc()).all()
    received = SwapRequest.query.filter_by(receiver_id=current_user.id).order_by(SwapRequest.created_at.desc()).all()
    unread = get_unread_count(current_user.id)
    return render_template('swaps.html', sent=sent, received=received, unread=unread)


# ─── Messaging Routes ─────────────────────────────────────────────────────────

@app.route('/messages')
@login_required
def messages():
    convos = db.session.execute(db.text("""
        SELECT DISTINCT
            CASE WHEN sender_id = :uid THEN receiver_id ELSE sender_id END as other_id
        FROM messages
        WHERE sender_id = :uid OR receiver_id = :uid
    """), {'uid': current_user.id}).fetchall()

    partners = []
    for row in convos:
        u = db.session.get(User, row[0])
        if u:
            last = Message.query.filter(
                db.or_(
                    db.and_(Message.sender_id == current_user.id, Message.receiver_id == u.id),
                    db.and_(Message.sender_id == u.id, Message.receiver_id == current_user.id),
                )
            ).order_by(Message.created_at.desc()).first()
            unread_count = Message.query.filter_by(sender_id=u.id, receiver_id=current_user.id, read=False).count()
            partners.append({'user': u, 'last': last, 'unread': unread_count})

    unread = get_unread_count(current_user.id)
    return render_template('messages.html', partners=partners, unread=unread)


@app.route('/messages/<int:other_id>')
@login_required
def chat(other_id):
    other = db.session.get(User, other_id)
    if not other:
        return redirect(url_for('messages'))

    msgs = Message.query.filter(
        db.or_(
            db.and_(Message.sender_id == current_user.id, Message.receiver_id == other_id),
            db.and_(Message.sender_id == other_id, Message.receiver_id == current_user.id),
        )
    ).order_by(Message.created_at.asc()).all()

    Message.query.filter_by(sender_id=other_id, receiver_id=current_user.id, read=False).update({'read': True})
    db.session.commit()
    cache_del(f'unread:{current_user.id}')

    unread = get_unread_count(current_user.id)
    return render_template('chat.html', other=other, messages=msgs, unread=unread)


@app.route('/api/messages/<int:other_id>', methods=['POST'])
@login_required
def send_message(other_id):
    content = request.json.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Empty message'}), 400

    msg = Message(sender_id=current_user.id, receiver_id=other_id, content=content)
    db.session.add(msg)
    db.session.commit()
    cache_del(f'unread:{other_id}')

    payload = {
        'id': msg.id,
        'content': content,
        'sender_id': current_user.id,
        'sender_name': current_user.name,
        'ts': msg.created_at.strftime('%H:%M'),
    }
    socketio.emit('new_message', payload, room=f'chat_{min(current_user.id, other_id)}_{max(current_user.id, other_id)}')
    notify_user(other_id, 'message', f'{current_user.name}: {content[:60]}')
    return jsonify(payload)


# ─── SocketIO ─────────────────────────────────────────────────────────────────

@socketio.on('join')
def on_join(data):
    if current_user.is_authenticated:
        join_room(f'user_{current_user.id}')
        if 'other_id' in data:
            other_id = int(data['other_id'])
            room = f'chat_{min(current_user.id, other_id)}_{max(current_user.id, other_id)}'
            join_room(room)


# ─── Seed Data ────────────────────────────────────────────────────────────────

def seed_db():
    if User.query.count() > 0:
        return
    import random
    samples = [
        ('Priya R.', 'priya@example.com', 'Bangalore', 'Figma', 'Python', 'teal', 4.9, 22, 18),
        ('Arjun K.', 'arjun@example.com', 'Mumbai', 'Guitar', 'React', 'purple', 4.7, 9, 7),
        ('Sneha M.', 'sneha@example.com', 'Delhi', 'French', 'Excel', 'coral', 4.8, 14, 11),
        ('Rahul V.', 'rahul@example.com', 'Pune', 'Yoga', 'Video editing', 'amber', 0.0, 0, 0),
        ('Nisha K.', 'nisha@example.com', 'Chennai', 'SQL', 'Drawing', 'blue', 0.0, 0, 0),
        ('Dev S.', 'dev@example.com', 'Kolkata', 'FastAPI', 'Tabla', 'pink', 0.0, 0, 0),
    ]
    colors = ['teal','purple','coral','amber','blue','pink']
    for name, email, city, offer, want, color, rating, reviews, sessions in samples:
        u = User(name=name, email=email, city=city,
                 offer_skill=offer, want_skill=want,
                 avatar_color=color,
                 avatar_initials=name[:2].upper(),
                 rating=rating, review_count=reviews, sessions_done=sessions)
        u.set_password('password123')
        db.session.add(u)
    db.session.commit()

with app.app_context():
    db.create_all()
    seed_db()
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_db()
    socketio.run(app, debug=True, port=5000)
