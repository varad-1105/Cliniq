from flask import Flask
from config import Config
from app.extensions import db, login_manager
from app.models.user import User
from app.routes.auth import auth
from app.routes.dashboard import dashboard


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    app.register_blueprint(auth)
    app.register_blueprint(dashboard)

    @app.route("/")
    def home():
        return "ClinIQ is Running"

    with app.app_context():
        db.create_all()

    return app
