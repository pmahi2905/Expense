from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Transaction, Budget
from datetime import datetime
from dotenv import load_dotenv
import os
import requests

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'expenzo-super-secret-key-2024')
database_url = os.getenv('DATABASE_URL', 'sqlite:///expenzo.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5000/auth/google/callback')

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if not name or not email or not password:
            flash('All fields are required.', 'error')
            return redirect(url_for('register'))
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
            return redirect(url_for('register'))
        user = User(name=name, email=email, password=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f'Welcome to Expenzo, {name}!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.password and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/auth/google')
def google_login():
    google_auth_url = (
        'https://accounts.google.com/o/oauth2/v2/auth'
        f'?client_id={GOOGLE_CLIENT_ID}'
        f'&redirect_uri={GOOGLE_REDIRECT_URI}'
        '&response_type=code'
        '&scope=openid email profile'
    )
    return redirect(google_auth_url)

@app.route('/auth/google/callback')
def google_callback():
    code = request.args.get('code')
    if not code:
        flash('Google login failed.', 'error')
        return redirect(url_for('login'))
    try:
        token_response = requests.post('https://oauth2.googleapis.com/token', data={
            'code': code,
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri': GOOGLE_REDIRECT_URI,
            'grant_type': 'authorization_code'
        })
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        if not access_token:
            flash('Google login failed. Please try again.', 'error')
            return redirect(url_for('login'))
        user_info = requests.get('https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        ).json()
        google_id = user_info.get('id')
        email = user_info.get('email')
        name = user_info.get('name')
        avatar = user_info.get('picture')
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(name=name, email=email, google_id=google_id, avatar=avatar)
            db.session.add(user)
            db.session.commit()
        else:
            user.google_id = google_id
            user.avatar = avatar
            db.session.commit()
        login_user(user)
        flash(f'Welcome, {name}!', 'success')
        return redirect(url_for('dashboard'))
    except Exception as e:
        flash('Google login failed. Please use email login instead.', 'error')
        return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    now = datetime.now()
    month = request.args.get('month', now.month, type=int)
    year = request.args.get('year', now.year, type=int)
    transactions = Transaction.query.filter_by(user_id=current_user.id).filter(
        db.extract('month', Transaction.date) == month,
        db.extract('year', Transaction.date) == year
    ).order_by(Transaction.date.desc()).all()
    total_spent = sum(t.amount for t in transactions)
    budgets = Budget.query.filter_by(user_id=current_user.id).all()
    total_budget = sum(b.amount for b in budgets)
    remaining = total_budget - total_spent
    categories = {}
    for t in transactions:
        categories[t.category] = categories.get(t.category, 0) + t.amount
    budget_progress = []
    for b in budgets:
        spent = categories.get(b.category, 0)
        pct = round((spent / b.amount) * 100) if b.amount > 0 else 0
        budget_progress.append({
            'category': b.category,
            'budget': b.amount,
            'spent': spent,
            'pct': min(pct, 100),
            'over': pct > 100
        })
    return render_template('dashboard.html',
        transactions=transactions[:5],
        all_count=len(transactions),
        total_spent=total_spent,
        total_budget=total_budget,
        remaining=remaining,
        categories=categories,
        budget_progress=budget_progress,
        month=month, year=year,
        month_name=datetime(year, month, 1).strftime('%B %Y')
    )

@app.route('/transactions', methods=['GET', 'POST'])
@login_required
def transactions():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        amount = request.form.get('amount')
        category = request.form.get('category')
        date_str = request.form.get('date')
        note = request.form.get('note', '').strip()
        if not name or not amount or not category or not date_str:
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('transactions'))
        t = Transaction(
            user_id=current_user.id,
            name=name,
            amount=float(amount),
            category=category,
            date=datetime.strptime(date_str, '%Y-%m-%d'),
            note=note
        )
        db.session.add(t)
        db.session.commit()
        flash('Transaction added successfully!', 'success')
        return redirect(url_for('transactions'))
    category_filter = request.args.get('category', '')
    query = Transaction.query.filter_by(user_id=current_user.id)
    if category_filter:
        query = query.filter_by(category=category_filter)
    all_transactions = query.order_by(Transaction.date.desc()).all()
    return render_template('transactions.html',
        transactions=all_transactions,
        category_filter=category_filter
    )

@app.route('/transactions/delete/<int:id>')
@login_required
def delete_transaction(id):
    t = Transaction.query.get_or_404(id)
    if t.user_id == current_user.id:
        db.session.delete(t)
        db.session.commit()
        flash('Transaction deleted.', 'success')
    return redirect(url_for('transactions'))

@app.route('/budgets', methods=['GET', 'POST'])
@login_required
def budgets():
    if request.method == 'POST':
        category = request.form.get('category')
        amount = request.form.get('amount')
        if not category or not amount:
            flash('Please fill in all fields.', 'error')
            return redirect(url_for('budgets'))
        existing = Budget.query.filter_by(user_id=current_user.id, category=category).first()
        if existing:
            existing.amount = float(amount)
            flash('Budget updated!', 'success')
        else:
            db.session.add(Budget(user_id=current_user.id, category=category, amount=float(amount)))
            flash('Budget created!', 'success')
        db.session.commit()
        return redirect(url_for('budgets'))
    all_budgets = Budget.query.filter_by(user_id=current_user.id).all()
    return render_template('budgets.html', budgets=all_budgets)

@app.route('/budgets/delete/<int:id>')
@login_required
def delete_budget(id):
    b = Budget.query.get_or_404(id)
    if b.user_id == current_user.id:
        db.session.delete(b)
        db.session.commit()
        flash('Budget deleted.', 'success')
    return redirect(url_for('budgets'))

if __name__ == '__main__':
    app.run(debug=True)