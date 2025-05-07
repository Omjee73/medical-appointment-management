from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import func
from datetime import datetime, timedelta
import io
from app import db, app
from models import Patient, Doctor, Appointment, TimeSlot
from forms import AppointmentForm, UserProfileForm

user_bp = Blueprint('user', __name__, url_prefix='/user')

# User authentication check
@user_bp.before_request
def check_user():
    if current_user.is_anonymous or current_user.user_type != 'patient':
        flash('You must be logged in as a patient to access this page.', 'danger')
        return redirect(url_for('auth.login'))

# User Dashboard
@user_bp.route('/')
@login_required
def dashboard():
    specialties = db.session.query(Doctor.specialization).distinct().all()
    specialties = [specialty[0] for specialty in specialties]
    
    # Filter by specialty if provided
    specialty = request.args.get('specialty')
    if specialty:
        doctors = Doctor.query.filter_by(specialization=specialty).all()
    else:
        doctors = Doctor.query.all()
    
    return render_template('user/dashboard.html', doctors=doctors, specialties=specialties, selected_specialty=specialty)

# Book Appointment
@user_bp.route('/book/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
def book_appointment(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    form = AppointmentForm()
    
    # Only allow future dates
    today = datetime.today().date()
    
    # Initialize form choices
    form.time_slot.choices = [(-1, 'No slots available')]
    
    # Populate time slots based on selected date
    if request.method == 'GET':
        selected_date_str = request.args.get('date', today.strftime('%Y-%m-%d'))
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            
            # Check if date is valid (doctor works on this day and date is in future)
            day_name = selected_date.strftime('%A')
            if day_name in doctor.available_days_list and selected_date >= today:
                try:
                    # Generate slots for that day if not already generated
                    existing_slots = TimeSlot.query.filter_by(doctor_id=doctor_id, date=selected_date).all()
                    
                    if not existing_slots:
                        # Generate time slots based on doctor's schedule
                        start_hour, start_minute = map(int, doctor.start_time.split(':'))
                        end_hour, end_minute = map(int, doctor.end_time.split(':'))
                        
                        start_datetime = datetime.combine(selected_date, datetime.min.time().replace(hour=start_hour, minute=start_minute))
                        end_datetime = datetime.combine(selected_date, datetime.min.time().replace(hour=end_hour, minute=end_minute))
                        
                        current_time = start_datetime
                        while current_time < end_datetime:
                            slot_time = current_time.strftime('%H:%M')
                            new_slot = TimeSlot(
                                doctor_id=doctor_id,
                                date=selected_date,
                                start_time=slot_time,
                                is_booked=False
                            )
                            db.session.add(new_slot)
                            current_time += timedelta(minutes=doctor.slot_duration)
                        
                        db.session.commit()
                    
                    # Get available slots for the form dropdown
                    available_slots = TimeSlot.query.filter_by(
                        doctor_id=doctor_id,
                        date=selected_date,
                        is_booked=False
                    ).all()
                    
                    if available_slots:
                        form.time_slot.choices = [(slot.id, slot.start_time) for slot in available_slots]
                    form.date.data = selected_date
                except Exception as e:
                    app.logger.error(f"Error generating time slots: {str(e)}")
                    db.session.rollback()
            
        except Exception as e:
            app.logger.error(f"Error parsing date: {str(e)}")
            form.date.data = today
    
    # Process form submission
    if form.validate_on_submit() and form.time_slot.data != -1:
        try:
            # Use a new transaction
            db.session.begin_nested()
            
            selected_slot = TimeSlot.query.get(form.time_slot.data)
            
            # Verify slot exists and is not booked
            if selected_slot and not selected_slot.is_booked:
                # Mark slot as booked
                selected_slot.is_booked = True
                
                # Create appointment
                new_appointment = Appointment(
                    patient_id=current_user.id,
                    doctor_id=doctor_id,
                    slot_id=selected_slot.id,
                    date=form.date.data,
                    time=selected_slot.start_time,
                    status='pending'  # Initial status is pending
                )
                
                db.session.add(new_appointment)
                db.session.commit()
                
                flash('Appointment booked successfully! Waiting for admin approval.', 'success')
                return redirect(url_for('user.appointments'))
            else:
                db.session.rollback()
                flash('Selected time slot is no longer available.', 'danger')
        except Exception as e:
            # Rollback in case of any error
            db.session.rollback()
            app.logger.error(f"Error booking appointment: {str(e)}")
            flash('An error occurred while booking your appointment. Please try again.', 'danger')
    
    # Get available dates (next 7 days where doctor is available)
    available_dates = []
    for i in range(30):  # Check next 30 days
        check_date = today + timedelta(days=i)
        day_name = check_date.strftime('%A')
        if day_name in doctor.available_days_list:
            available_dates.append(check_date)
        if len(available_dates) >= 7:  # Limit to 7 available dates
            break
    
    return render_template(
        'user/book_appointment.html',
        form=form,
        doctor=doctor,
        patient=current_user,
        available_dates=available_dates,
        selected_date=form.date.data if form.date.data else today,
        today=today
    )

# View All Appointments
@user_bp.route('/appointments')
@login_required
def appointments():
    try:
        user_appointments = Appointment.query.filter_by(
            patient_id=current_user.id
        ).join(Doctor).all()
        
        # Update status for completed appointments
        today = datetime.today().date()
        
        # Use a transaction for status updates
        db.session.begin_nested()
        
        for appointment in user_appointments:
            if appointment.status == 'approved' and appointment.date < today:
                appointment.status = 'completed'
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error loading appointments: {str(e)}")
        flash("There was an error loading your appointments.", "danger")
        user_appointments = []
    
    return render_template('user/appointment.html', appointments=user_appointments)

# Generate Receipt
@user_bp.route('/receipt/<int:appointment_id>')
@login_required
def receipt(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    
    # Ensure the appointment belongs to the current user
    if appointment.patient_id != current_user.id:
        flash('You do not have permission to view this receipt.', 'danger')
        return redirect(url_for('user.appointments'))
    
    # Check if appointment is approved or completed
    if appointment.status not in ['approved', 'completed']:
        flash('Receipt is only available for approved or completed appointments.', 'warning')
        return redirect(url_for('user.appointments'))
    
    doctor = Doctor.query.get(appointment.doctor_id)
    
    return render_template('user/receipt.html', appointment=appointment, doctor=doctor, patient=current_user)

# User Analytics
@user_bp.route('/summary')
@login_required
def summary():
    # Initialize values with defaults
    total_appointments = 0
    status_labels = []
    status_counts = []
    accepted_count = 0
    rejected_count = 0
    pending_count = 0
    completed_count = 0
    time_labels = []
    time_counts = []
    specialist_labels = []
    specialist_counts = []
    
    try:
        # Get total appointment count
        total_appointments = Appointment.query.filter_by(patient_id=current_user.id).count()
        
        # Get the user's appointment count by status
        appointment_status = db.session.query(
            Appointment.status,
            func.count(Appointment.id)
        ).filter(
            Appointment.patient_id == current_user.id
        ).group_by(Appointment.status).all()
        
        for status, count in appointment_status:
            status_labels.append(status.capitalize())
            status_counts.append(count)
            
            if status == 'approved':
                accepted_count += count
            elif status == 'completed':
                completed_count += count
                accepted_count += count  # Completed appointments were also accepted
            elif status == 'rejected':
                rejected_count += count
            elif status == 'pending':
                pending_count += count
        
        # Get preferred time slots
        time_preferences = db.session.query(
            Appointment.time,
            func.count(Appointment.id)
        ).filter(
            Appointment.patient_id == current_user.id
        ).group_by(Appointment.time).order_by(func.count(Appointment.id).desc()).limit(5).all()
        
        time_labels = [time[0] for time in time_preferences]
        time_counts = [time[1] for time in time_preferences]
        
        # Get most visited specialist types
        specialist_preferences = db.session.query(
            Doctor.specialization,
            func.count(Appointment.id)
        ).filter(
            Appointment.patient_id == current_user.id
        ).join(Doctor).group_by(Doctor.specialization).order_by(func.count(Appointment.id).desc()).all()
        
        specialist_labels = [sp[0] for sp in specialist_preferences]
        specialist_counts = [sp[1] for sp in specialist_preferences]
        
    except Exception as e:
        app.logger.error(f"Error fetching summary data: {str(e)}")
        # If there's any error, continue with empty data rather than crashing
        flash("There was an error loading your summary data. Some charts may not display correctly.", "warning")
    
    # Get appointment history by month
    current_year = datetime.now().year
    now = datetime.now()
    try:
        # For PostgreSQL
        monthly_data = db.session.query(
            func.extract('month', Appointment.date).label('month'),
            func.count(Appointment.id)
        ).filter(
            Appointment.patient_id == current_user.id,
            func.extract('year', Appointment.date) == current_year
        ).group_by('month').all()
    except Exception:
        # Fallback for SQLite
        try:
            monthly_data = db.session.query(
                func.strftime('%m', Appointment.date).label('month'),
                func.count(Appointment.id)
            ).filter(
                Appointment.patient_id == current_user.id,
                func.strftime('%Y', Appointment.date) == str(current_year)
            ).group_by('month').all()
        except Exception as e:
            app.logger.error(f"Error getting monthly data: {str(e)}")
            monthly_data = []
    
    months = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_counts = [0] * 12
    
    for month, count in monthly_data:
        try:
            # Check if it's a string (SQLite) or number (PostgreSQL)
            if isinstance(month, str) and month in months:
                monthly_counts[months.index(month)] = count
            elif isinstance(month, (int, float)):
                # PostgreSQL returns month as a number (1-12)
                month_idx = int(month) - 1
                if 0 <= month_idx < 12:
                    monthly_counts[month_idx] = count
        except (ValueError, TypeError) as e:
            app.logger.error(f"Error processing month {month}: {str(e)}")
    
    return render_template(
        'user/summary.html',
        status_labels=status_labels,
        status_counts=status_counts,
        time_labels=time_labels,
        time_counts=time_counts,
        specialist_labels=specialist_labels,
        specialist_counts=specialist_counts,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        pending_count=pending_count,
        completed_count=completed_count,
        total_appointments=total_appointments,
        month_names=month_names,
        monthly_counts=monthly_counts,
        now=datetime.now()
    )

# User Profile
@user_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = UserProfileForm(obj=current_user)
    
    if form.validate_on_submit():
        # Verify current password
        if check_password_hash(current_user.password_hash, form.current_password.data):
            current_user.name = form.name.data
            current_user.email = form.email.data
            current_user.phone = form.phone.data
            current_user.address = form.address.data
            current_user.gender = form.gender.data
            current_user.age = form.age.data
            
            # Update password if provided
            if form.new_password.data:
                current_user.password_hash = generate_password_hash(form.new_password.data)
            
            db.session.commit()
            flash('Your profile has been updated!', 'success')
            return redirect(url_for('user.edit_profile'))
        else:
            flash('Current password is incorrect.', 'danger')
    
    return render_template('user/edit_profile.html', form=form)
