# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, time
import pytz

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///volei.db'
db = SQLAlchemy(app)

BR_TIMEZONE = pytz.timezone('America/Sao_Paulo')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(80), nullable=False)

class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    registration_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='CONFIRMADO')
    position = db.Column(db.Integer)
    game_date = db.Column(db.Date, nullable=False)
    user = db.relationship('User', backref='registrations')

def get_active_lists():
    now = datetime.now(BR_TIMEZONE)
    today = now.date()
    tomorrow = today + timedelta(days=1)
    
    lists = []
    
    # Lista de hoje
    today_open = datetime.combine(today - timedelta(days=1), time(12, 0))
    today_close = datetime.combine(today, time(19, 0))
    today_open = BR_TIMEZONE.localize(today_open)
    today_close = BR_TIMEZONE.localize(today_close)
    
    if today_open <= now <= today_close:
        lists.append(today)
        
    # Lista de amanhã
    tomorrow_open = datetime.combine(today, time(12, 0))
    tomorrow_close = datetime.combine(tomorrow, time(19, 0))
    tomorrow_open = BR_TIMEZONE.localize(tomorrow_open)
    tomorrow_close = BR_TIMEZONE.localize(tomorrow_close)
    
    if tomorrow_open <= now <= tomorrow_close:
        lists.append(tomorrow)
        
    return lists

def is_list_open(game_date):
    now = datetime.now(BR_TIMEZONE)
    open_time = datetime.combine(game_date - timedelta(days=1), time(12, 0))
    close_time = datetime.combine(game_date, time(19, 0))
    
    open_time = BR_TIMEZONE.localize(open_time)
    close_time = BR_TIMEZONE.localize(close_time)
    
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
                         datetime=datetime)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        
        if user and check_password_hash(user.password, request.form['password']):
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
        if User.query.filter_by(username=request.form['username']).first():
            flash('Nome de usuário já existe')
            return redirect(url_for('register_user'))
            
        user = User(
            username=request.form['username'],
            password=generate_password_hash(request.form['password']),
            name=request.form['name']
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Conta criada com sucesso!')
        return redirect(url_for('login'))
    return render_template('register_user.html')

@app.route('/register', methods=['POST'])
def register():
    if not session.get('user_id'):
        flash('Faça login primeiro')
        return redirect(url_for('login'))

    game_date = datetime.strptime(request.form['game_date'], '%Y-%m-%d').date()
    
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
    
    new_reg = Registration(
        user_id=session['user_id'],
        name=session['name'],
        registration_time=datetime.now(BR_TIMEZONE),
        game_date=game_date,
        status='CONFIRMADO' if main_count < 22 else 'LISTA_ESPERA',
        position=main_count + 1 if main_count < 22 else waiting_count + 1
    )
    
    db.session.add(new_reg)
    db.session.commit()
    
    flash('Inscrição realizada com sucesso!')
    return redirect(url_for('index'))

@app.route('/cancel', methods=['POST'])
def cancel():
    if not session.get('user_id'):
        flash('Faça login primeiro')
        return redirect(url_for('login'))
    
    game_date = datetime.strptime(request.form['game_date'], '%Y-%m-%d').date()
    
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
            
            for i, reg in enumerate(waiting_list[1:], 1):
                reg.position = i
    
    db.session.delete(registration)
    db.session.commit()
    
    flash('Inscrição cancelada com sucesso')
    return redirect(url_for('index'))

def init_db():
    with app.app_context():
        db.drop_all()
        db.create_all()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)