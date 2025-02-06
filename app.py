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

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///volei.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Timezone configuration
BR_TIMEZONE = ZoneInfo('America/Sao_Paulo')

# Models
class User(db.Model):
    __tablename__ = 'user'  # Explicitly set table name
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)  # Increased length
    password = db.Column(db.String(255), nullable=False)  # Increased length
    name = db.Column(db.String(255), nullable=False)  # Increased length

class Registration(db.Model):
    __tablename__ = 'registration'  # Explicitly set table name
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)  # Increased length
    registration_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='CONFIRMADO')
    position = db.Column(db.Integer)
    game_date = db.Column(db.Date, nullable=False)
    user = db.relationship('User', backref='registrations')

# Create tables
def init_db():
    with app.app_context():
        db.create_all()
        db.session.commit()

# Uncomment the following line during initial setup
init_db()

# Rest of the code remains the same... (all previous routes and functions)

@app.route('/create_test_user')
def create_test_user():
    try:
        # Truncate values to ensure they fit within column limits
        username = 'teste'[:255]
        name = 'Usuário Teste'[:255]
        
        test_user = User(
            username=username,
            password=generate_password_hash('123456'),
            name=name
        )
        db.session.add(test_user)
        db.session.commit()
        return 'Test user created successfully'
    except Exception as e:
        db.session.rollback()
        return f'Error creating user: {str(e)}'

# Additional debug route to help diagnose issues
@app.route('/user_model_debug')
def user_model_debug():
    try:
        # Print out column information
        columns = User.__table__.columns
        column_info = {column.name: {
            'type': str(column.type),
            'primary_key': column.primary_key,
            'nullable': column.nullable,
            'unique': column.unique
        } for column in columns}
        
        return {
            'status': 'OK',
            'columns': column_info
        }
    except Exception as e:
        return {
            'status': 'ERROR',
            'error': str(e)
        }

if __name__ == '__main__':
    app.run(debug=True)

