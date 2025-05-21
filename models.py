from datetime import datetime
from flask_login import UserMixin
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

# Base User model for authentication
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    user_type = db.Column(db.String(10), nullable=False)  # 'admin' or 'patient'
    
    __mapper_args__ = {
        'polymorphic_identity': 'user',
        'polymorphic_on': user_type
    }
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Admin model
class Admin(User):
    __tablename__ = 'admins'
    
    id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    
    __mapper_args__ = {
        'polymorphic_identity': 'admin',
    }

# Patient model
class Patient(User):
    __tablename__ = 'patients'
    
    id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    is_blocked = db.Column(db.Boolean, default=False)
    
    # Relationships
    appointments = db.relationship('Appointment', backref='patient', lazy=True)
    
    __mapper_args__ = {
        'polymorphic_identity': 'patient',
    }

# Doctor model
class Doctor(db.Model):
    __tablename__ = 'doctors'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    fees = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(200), nullable=False)
    start_time = db.Column(db.String(5), nullable=False)  # Format: HH:MM
    end_time = db.Column(db.String(5), nullable=False)    # Format: HH:MM
    slot_duration = db.Column(db.Integer, nullable=False)  # in minutes
    available_days = db.Column(db.String(100), nullable=False)  # comma-separated days
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    time_slots = db.relationship('TimeSlot', backref='doctor', lazy=True, cascade="all, delete-orphan")
    appointments = db.relationship('Appointment', backref='doctor', lazy=True)
    
    @property
    def available_days_list(self):
        return self.available_days.split(',')

# TimeSlot model
class TimeSlot(db.Model):
    __tablename__ = 'time_slots'
    
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(5), nullable=False)  # Format: HH:MM
    is_booked = db.Column(db.Boolean, default=False)
    
    # Add unique constraint to ensure no duplicate slots
    __table_args__ = (
        db.UniqueConstraint('doctor_id', 'date', 'start_time', name='unique_time_slot'),
    )

# Appointment model
class Appointment(db.Model):
    __tablename__ = 'appointments'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey('time_slots.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(5), nullable=False)  # Format: HH:MM
    status = db.Column(db.String(20), default='pending')  # 'pending', 'approved', 'rejected', 'completed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with TimeSlot
    time_slot = db.relationship('TimeSlot', backref='appointment', uselist=False)
    
    @property
    def is_completed(self):
        # Only return True if status is explicitly set to 'completed'
        return self.status == 'completed'
