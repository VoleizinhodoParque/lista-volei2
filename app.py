from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate  # Nova importação
from sqlalchemy_utils import database_exists
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import os
from dotenv import load_dotenv

# Adicione isso próximo às importações de migrate
from flask_migrate import init, migrate as migrate_command, upgrade

load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback_secret_key')

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///volei.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)
migrate = Migrate(app, db)  # Nova linha para migração

# Timezone configuration
BR_TIMEZONE = ZoneInfo('America/Sao_Paulo')

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)

class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    registration_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='CONFIRMADO')
    position = db.Column(db.Integer)
    game_date = db.Column(db.Date, nullable=False)
    user = db.relationship('User', backref='registrations')

# Utility Functions
def get_active_lists():
    now = datetime.now(BR_TIMEZONE)
    today = now.date()
    tomorrow = today + timedelta(days=1)
    
    lists = []
    
    # Lista de hoje
    today_open = datetime.combine(today - timedelta(days=1), time(12, 0), tzinfo=BR_TIMEZONE)
    today_close = datetime.combine(today, time(21, 0), tzinfo=BR_TIMEZONE)
    
    if today_open <= now <= today_close:
        lists.append(today)
        
    # Lista de amanhã
    tomorrow_open = datetime.combine(today, time(12, 0), tzinfo=BR_TIMEZONE)
    tomorrow_close = datetime.combine(tomorrow, time(21, 0), tzinfo=BR_TIMEZONE)
    
    if tomorrow_open <= now <= tomorrow_close:
        lists.append(tomorrow)
        
    return lists

def is_list_open(game_date):
    now = datetime.now(BR_TIMEZONE)
    open_time = datetime.combine(game_date - timedelta(days=1), time(12, 0), tzinfo=BR_TIMEZONE)
    close_time = datetime.combine(game_date, time(21, 0), tzinfo=BR_TIMEZONE)
    
    return open_time <= now <= close_time

# Routes
@app.route('/')
def index():
    active_dates = get_active_lists()
    lists_data = []
    
    for game_date in active_dates:
        main_list = Registration.query.filter_by(
            game_date=game_date,
            status='CONFIRMADO'
        ).order_by(Registration.position).all()
        
        waiting_list = Registration.query.filter_by(
            game_date=game_date,
            status='LISTA_ESPERA'
        ).order_by(Registration.position).all()
        
        user_registered = False
        if session.get('user_id'):
            user_registered = Registration.query.filter_by(
                user_id=session['user_id'],
                game_date=game_date
            ).first() is not None
            
        lists_data.append({
            'game_date': game_date,
            'main_list': main_list,
            'waiting_list': waiting_list,
            'user_registered': user_registered,
            'is_open': is_list_open(game_date)
        })
    
    return render_template('index.html',
                         lists_data=lists_data,
                         datetime=datetime)

# Adicione essa função no final do arquivo, antes do if __name__ == '__main__':
def initialize_migrations():
    try:
        import os
        if not os.path.exists('migrations'):
            init()
            migrate_command(message="Initial migration")
            upgrade()
    except Exception as e:
        print(f"Migration initialization error: {e}")

if __name__ == '__main__':
    initialize_migrations()
    app.run(debug=True)

