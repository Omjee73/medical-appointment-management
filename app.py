import os
import logging
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy
db = SQLAlchemy(model_class=Base)

# Create the Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///medical_app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize SQLAlchemy with the app
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

# Import models after db is defined to avoid circular imports
with app.app_context():
    from models import User, Patient, Admin, Doctor, Appointment, TimeSlot
    
    # Create database tables
    db.create_all()
    
    # Create default admin accounts if they don't exist
    from werkzeug.security import generate_password_hash
    
    admin_accounts = [
        {"email": "admin1@medical.com", "password": "admin123", "name": "Admin One"},
        {"email": "admin2@medical.com", "password": "admin456", "name": "Admin Two"}
    ]
    
    for admin_data in admin_accounts:
        admin = Admin.query.filter_by(email=admin_data["email"]).first()
        if not admin:
            new_admin = Admin(
                email=admin_data["email"],
                password_hash=generate_password_hash(admin_data["password"]),
                name=admin_data["name"]
            )
            db.session.add(new_admin)
    
    db.session.commit()

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Register blueprints
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.user import user_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(user_bp)

# Root route redirects to login page
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.user_type == 'admin':
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('user.dashboard'))
    return redirect(url_for('auth.login'))

# Jinja template filters
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d'):
    if value:
        return value.strftime(format)
    return ""

# Context processor to pass common variables to templates
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
