from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        if not self.password.startswith(("scrypt:", "pbkdf2:")):
            return self.password == password

        return check_password_hash(self.password, password)

    def password_needs_hashing(self):
        return not self.password.startswith(("scrypt:", "pbkdf2:"))

    def __repr__(self):
        return f"<User {self.name}>"
