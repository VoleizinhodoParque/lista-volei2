from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import os
from dotenv import load_dotenv

from models import db, User, Registration

load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if os.environ.get('RENDER'):
        raise RuntimeError('SECRET_KEY environment variable must be set in production')
    SECRET_KEY = 'dev-only-insecure-key'
app.config['SECRET_KEY'] = SECRET_KEY

# Database configuration - PostgreSQL in production, local SQLite for development
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

if DATABASE_URL:
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    os.makedirs(app.instance_path, exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'volei.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=[])

# Timezone configuration
BR_TIMEZONE = ZoneInfo('America/Sao_Paulo')

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

def limpar_registros_antigos():
    try:
        # Data atual no timezone do Brasil
        hoje = datetime.now(BR_TIMEZONE).date()
        
        # Remove registros de jogos que já passaram há mais de 7 dias
        data_limite = hoje - timedelta(days=7)
        
        registros_antigos = Registration.query.filter(
            Registration.game_date < data_limite
        ).all()
        
        total_removidos = len(registros_antigos)
        
        for registro in registros_antigos:
            db.session.delete(registro)
        
        db.session.commit()
        print(f"{total_removidos} registros de jogos antigos removidos")
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao remover registros antigos: {e}")

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
@limiter.limit('10 per minute')
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

    try:
        # Lock existing registrations for this date so concurrent sign-ups
        # (including double submits from the same user) can't read the same
        # counts and collide on the same position or duplicate a signup.
        regs_for_date = Registration.query.filter_by(
            game_date=game_date
        ).with_for_update().all()

        if any(r.user_id == session['user_id'] for r in regs_for_date):
            flash('Você já está inscrito para este dia')
            db.session.rollback()
            return redirect(url_for('index'))

        main_count = sum(1 for r in regs_for_date if r.status == 'CONFIRMADO')
        waiting_count = sum(1 for r in regs_for_date if r.status == 'LISTA_ESPERA')

        if main_count >= 22 and waiting_count >= 50:
            flash('Todas as vagas preenchidas')
            db.session.rollback()
            return redirect(url_for('index'))

        # Correct timezone handling for registration
        now = datetime.now(BR_TIMEZONE)
        utc_time = now.astimezone(ZoneInfo('UTC'))

        new_reg = Registration(
            user_id=session['user_id'],
            name=session['name'],
            registration_time=utc_time,  # Save in UTC
            game_date=game_date,
            status='CONFIRMADO' if main_count < 22 else 'LISTA_ESPERA',
            position=main_count + 1 if main_count < 22 else waiting_count + 1
        )

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

    try:
        # Lock all registrations for this date up front so a concurrent
        # register/cancel on the same date can't interleave with the
        # position shifting below.
        regs_for_date = Registration.query.filter_by(
            game_date=game_date
        ).with_for_update().all()

        registration = next(
            (r for r in regs_for_date if r.user_id == session['user_id']), None
        )

        if not registration:
            flash('Você não está inscrito para este dia')
            db.session.rollback()
            return redirect(url_for('index'))

        if registration.status == 'CONFIRMADO':
            main_list = sorted(
                (r for r in regs_for_date if r.status == 'CONFIRMADO' and r.id != registration.id),
                key=lambda x: x.registration_time
            )
            waiting_list = sorted(
                (r for r in regs_for_date if r.status == 'LISTA_ESPERA'),
                key=lambda x: x.registration_time
            )

            # Se lista principal tem menos de 22 e há espera, promove o primeiro
            if len(main_list) < 22 and waiting_list:
                first_waiting = waiting_list[0]
                first_waiting.status = 'CONFIRMADO'
                main_list.append(first_waiting)
                waiting_list = waiting_list[1:]

            # Reordena lista principal
            for i, reg in enumerate(sorted(main_list, key=lambda x: x.registration_time), start=1):
                reg.position = i

            # Reordena lista de espera
            for i, reg in enumerate(waiting_list, start=1):
                reg.position = i
        else:
            waiting_list = sorted(
                (r for r in regs_for_date if r.status == 'LISTA_ESPERA' and r.id != registration.id),
                key=lambda x: x.registration_time
            )

            # Reordena lista de espera
            for i, reg in enumerate(waiting_list, start=1):
                reg.position = i

        # Remove a inscrição cancelada
        db.session.delete(registration)
        db.session.commit()
        flash('Inscrição cancelada com sucesso!')
    except Exception as e:
        db.session.rollback()
        flash('Ocorreu um erro ao cancelar a inscrição.')
        print(f"Error canceling: {str(e)}")

    return redirect(url_for('index'))

# Chamada de limpeza antes do bloco principal
with app.app_context():
    limpar_registros_antigos()

if __name__ == '__main__':
   app.run(debug=True)


