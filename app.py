import os
import logging
from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request
from flask_login import LoginManager, current_user
from werkzeug.security import generate_password_hash

# Import extensions and models
from extensions import db
from models import User, Patient, Admin, Doctor, Appointment, TimeSlot
from app_factory import app

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
login_manager.session_protection = None  # Disable session protection to allow multiple logins

# Create database tables and default admins
with app.app_context():
    db.create_all()

    # Create default admin accounts if they don't exist
    admin_accounts = [
        {"email": "admin1@medical.com", "password": "admin123", "name": "Admin One"},
        {"email": "admin2@medical.com", "password": "admin456", "name": "Admin Two"}
    ]

    for admin_data in admin_accounts:
        existing_admin = Admin.query.filter_by(email=admin_data["email"]).first()
        if not existing_admin:
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
    return User.query.get(int(user_id))

# Register blueprints
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.user import user_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(user_bp)

# Root route redirects to appropriate dashboard
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

# Context processor to inject current time
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
