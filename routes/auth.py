from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from models import User, Patient, Admin
from forms import LoginForm, RegisterForm

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.user_type == 'admin':
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('user.dashboard'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and user.check_password(form.password.data):
            # Check if user type matches selected type
            if user.user_type != form.user_type.data:
                if form.user_type.data == 'admin':
                    flash('This email is not registered as an administrator account.', 'danger')
                else:
                    flash('This email is not registered as a patient account.', 'danger')
                return redirect(url_for('auth.login'))
            
            # Check if patient is blocked
            if user.user_type == 'patient' and user.is_blocked:
                flash('Your account has been blocked. Please contact the administrator.', 'danger')
                return redirect(url_for('auth.login'))
            
            login_user(user)
            next_page = request.args.get('next')
            
            if user.user_type == 'admin':
                return redirect(next_page or url_for('admin.dashboard'))
            else:
                return redirect(next_page or url_for('user.dashboard'))
        else:
            flash('Login failed. Please check your email and password.', 'danger')
    
    return render_template('login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegisterForm()
    
    if form.validate_on_submit():
        # Check if email already exists
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered. Please use a different email or login.', 'danger')
            return redirect(url_for('auth.register'))
        
        # Create new patient
        patient = Patient(
            email=form.email.data,
            name=form.name.data,
            phone=form.phone.data,
            address=form.address.data,
            gender=form.gender.data,
            age=form.age.data
        )
        patient.set_password(form.password.data)
        
        db.session.add(patient)
        db.session.commit()
        
        flash('Registration successful! You can now login.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    # Clear any session data to prevent conflicts when switching accounts
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
