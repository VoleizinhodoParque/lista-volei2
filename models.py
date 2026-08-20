from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

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
