from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, SelectMultipleField
from wtforms import IntegerField, DateField, TimeField, TextAreaField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, ValidationError
from wtforms.widgets import CheckboxInput
from datetime import datetime

# Authentication Forms
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    user_type = SelectField('Account Type', choices=[('patient', 'Patient'), ('admin', 'Administrator')], default='patient')
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    confirm_password = PasswordField(
        'Confirm Password', 
        validators=[DataRequired(), EqualTo('password', message='Passwords must match')]
    )
    phone = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=15)])
    address = TextAreaField('Address', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], validators=[DataRequired()])
    age = IntegerField('Age', validators=[DataRequired(), NumberRange(min=1, max=120)])
    submit = SubmitField('Register')

# Doctor Forms
class DoctorForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
    specialization = StringField('Specialization', validators=[DataRequired()])
    fees = IntegerField('Fees (in ₹)', validators=[DataRequired(), NumberRange(min=0)])
    address = TextAreaField('Address', validators=[DataRequired()])
    start_time = StringField('Start Time (HH:MM)', validators=[DataRequired()])
    end_time = StringField('End Time (HH:MM)', validators=[DataRequired()])
    slot_duration = IntegerField('Slot Duration (in minutes)', validators=[DataRequired(), NumberRange(min=10, max=120)])
    available_days = SelectMultipleField('Available Days', 
        choices=[
            ('Monday', 'Monday'),
            ('Tuesday', 'Tuesday'), 
            ('Wednesday', 'Wednesday'), 
            ('Thursday', 'Thursday'), 
            ('Friday', 'Friday'), 
            ('Saturday', 'Saturday'), 
            ('Sunday', 'Sunday')
        ],
        validators=[DataRequired()]
    )
    submit = SubmitField('Save Doctor')
    
    def validate_start_time(form, field):
        try:
            datetime.strptime(field.data, "%H:%M")
        except ValueError:
            raise ValidationError("Time must be in format HH:MM")
            
    def validate_end_time(form, field):
        try:
            start = datetime.strptime(form.start_time.data, "%H:%M")
            end = datetime.strptime(field.data, "%H:%M")
            if end <= start:
                raise ValidationError("End time must be after start time")
        except ValueError:
            raise ValidationError("Time must be in format HH:MM")

# Appointment Forms
class AppointmentForm(FlaskForm):
    date = DateField('Date', format='%Y-%m-%d', validators=[DataRequired()])
    time_slot = SelectField('Available Time Slots', validators=[DataRequired()], coerce=int)
    submit = SubmitField('Book Appointment')

# Admin Profile Form
class AdminProfileForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[Length(min=6, message='Password must be at least 6 characters long')])
    confirm_password = PasswordField(
        'Confirm New Password', 
        validators=[EqualTo('new_password', message='Passwords must match')]
    )
    submit = SubmitField('Update Profile')

# User Profile Form
class UserProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=15)])
    address = TextAreaField('Address', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], validators=[DataRequired()])
    age = IntegerField('Age', validators=[DataRequired(), NumberRange(min=1, max=120)])
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[Length(min=6, message='Password must be at least 6 characters long')])
    confirm_password = PasswordField(
        'Confirm New Password', 
        validators=[EqualTo('new_password', message='Passwords must match')]
    )
    submit = SubmitField('Update Profile')
