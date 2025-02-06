from app import app, db

if __name__ == '__main__':
    with app.app_context():
        from flask_migrate import Migrate, upgrade
        migrate = Migrate(app, db)
        upgrade()
