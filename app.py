from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils import database_exists
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback_secret_key')

# Database configuration - PostgreSQL
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
   DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Timezone configuration
BR_TIMEZONE = ZoneInfo('America/Sao_Paulo')

# Models
class User(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   username = db.Column(db.String(80), unique=True, nullable=False)
   password = db.Column(db.String(120), nullable=False)
   name = db.Column(db.String(80), nullable=False)

class Registration(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
   name = db.Column(db.String(80), nullable=False)
   registration_time = db.Column(db.DateTime(timezone=True), nullable=False)
   status = db.Column(db.String(20), default='CONFIRMADO')
   position = db.Column(db.Integer)
   game_date = db.Column(db.Date, nullable=False)
   user = db.relationship('User', backref='registrations')

def init_db():
   with app.app_context():
       try:
           db.create_all()
           print("Database tables created successfully")
       except Exception as e:
           print(f"Error creating database tables: {e}")

# Initialize database (only in production)
if os.environ.get('RENDER'):
   init_db()

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

@app.route('/debug')
def debug():
   from sqlalchemy import inspect
   inspector = inspect(db.engine)
   
   try:
       # Test connection
       tables = inspector.get_table_names()
       user_count = User.query.count() if 'user' in tables else 'Table not found'
       
       return {
           'status': 'OK',
           'database_url_type': app.config['SQLALCHEMY_DATABASE_URI'].split(':')[0],
           'tables': tables,
           'user_count': user_count,
           'tables_exist': {
               'user': 'user' in tables,
               'registration': 'registration' in tables
           }
       }
   except Exception as e:
       return {
           'status': 'ERROR',
           'error_type': type(e).__name__,
           'error_message': str(e)
       }

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
                        datetime=datetime,
                        BR_TIMEZONE=BR_TIMEZONE)

@app.route('/login', methods=['GET', 'POST'])
def login():
   if request.method == 'POST':
       username = request.form.get('username')
       password = request.form.get('password')
       
       if not username or not password:
           flash('Preencha todos os campos')
           return redirect(url_for('login'))
       
       user = User.query.filter_by(username=username).first()
       
       if user and check_password_hash(user.password, password):
           session['user_id'] = user.id
           session['name'] = user.name
           return redirect(url_for('index'))
           
       flash('Usuário ou senha incorretos')
   return render_template('login.html')

@app.route('/logout')
def logout():
   session.clear()
   return redirect(url_for('index'))

@app.route('/register_user', methods=['GET', 'POST'])
def register_user():
   if request.method == 'POST':
       username = request.form.get('username')
       password = request.form.get('password')
       name = request.form.get('name')
       
       if not username or not password or not name:
           flash('Preencha todos os campos')
           return redirect(url_for('register_user'))
           
       if User.query.filter_by(username=username).first():
           flash('Nome de usuário já existe')
           return redirect(url_for('register_user'))
           
       user = User(
           username=username,
           password=generate_password_hash(password),
           name=name
       )
       
       try:
           db.session.add(user)
           db.session.commit()
           flash('Conta criada com sucesso!')
           return redirect(url_for('login'))
       except Exception as e:
           db.session.rollback()
           flash('Ocorreu um erro ao criar a conta. Tente novamente.')
           print(f"Error creating user: {str(e)}")
   
   return render_template('register_user.html')

@app.route('/register', methods=['POST'])
def register():
   if not session.get('user_id'):
       flash('Faça login primeiro')
       return redirect(url_for('login'))

   game_date_str = request.form.get('game_date')
   if not game_date_str:
       flash('Data inválida')
       return redirect(url_for('index'))
   
   game_date = datetime.strptime(game_date_str, '%Y-%m-%d').date()
   
   if not is_list_open(game_date):
       flash('Lista fechada no momento')
       return redirect(url_for('index'))
   
   existing = Registration.query.filter_by(
       user_id=session['user_id'],
       game_date=game_date
   ).first()
   
   if existing:
       flash('Você já está inscrito para este dia')
       return redirect(url_for('index'))
   
   main_count = Registration.query.filter_by(
       game_date=game_date,
       status='CONFIRMADO'
   ).count()
   
   waiting_count = Registration.query.filter_by(
       game_date=game_date,
       status='LISTA_ESPERA'
   ).count()
   
   if main_count >= 22 and waiting_count >= 50:
       flash('Todas as vagas preenchidas')
       return redirect(url_for('index'))
   
   # Correct timezone handling
   now = datetime.now(BR_TIMEZONE)
   
   new_reg = Registration(
       user_id=session['user_id'],
       name=session['name'],
       registration_time=now,
       game_date=game_date,
       status='CONFIRMADO' if main_count < 22 else 'LISTA_ESPERA',
       position=main_count + 1 if main_count < 22 else waiting_count + 1
   )
   
   try:
       db.session.add(new_reg)
       db.session.commit()
       flash('Inscrição realizada com sucesso!')
   except Exception as e:
       db.session.rollback()
       flash('Ocorreu um erro ao realizar a inscrição. Tente novamente.')
       print(f"Error registering: {str(e)}")
   
   return redirect(url_for('index'))

@app.route('/cancel', methods=['POST'])
def cancel():
   if not session.get('user_id'):
       flash('Faça login primeiro')
       return redirect(url_for('login'))
   
   game_date_str = request.form.get('game_date')
   if not game_date_str:
       flash('Data inválida')
       return redirect(url_for('index'))
   
   game_date = datetime.strptime(game_date_str, '%Y-%m-%d').date()
   
   if not is_list_open(game_date):
       flash('Lista fechada no momento')
       return redirect(url_for('index'))
   
   registration = Registration.query.filter_by(
       user_id=session['user_id'],
       game_date=game_date
   ).first()
   
   if not registration:
       flash('Você não está inscrito para este dia')
       return redirect(url_for('index'))
   
   try:
       if registration.status == 'CONFIRMADO':
           first_waiting = Registration.query.filter_by(
               game_date=game_date,
               status='LISTA_ESPERA'
           ).order_by(Registration.position).first()
           
           if first_waiting:
               first_waiting.status = 'CONFIRMADO'
               first_waiting.position = registration.position
               
               waiting_list = Registration.query.filter_by(
                   game_date=game_date,
                   status='LISTA_ESPERA'
               ).order_by(Registration.position).all()
               
               for idx, reg in enumerate(waiting_list, start=first_waiting.position + 1):
                   reg.position = idx
       
       db.session.delete(registration)
       db.session.commit()
       flash('Inscrição cancelada com sucesso!')
   except Exception as e:
       db.session.rollback()
       flash('Ocorreu um erro ao cancelar a inscrição.')
       print(f"Error canceling: {str(e)}")
   
   return redirect(url_for('index'))

if __name__ == '__main__':
   app.run(debug=True)

