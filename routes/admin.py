from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import func, extract
from datetime import datetime, timedelta, date
from app import db
from models import Admin, Patient, Doctor, Appointment, TimeSlot, User
from forms import DoctorForm, AdminProfileForm

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Admin authentication check
@admin_bp.before_request
def check_admin():
    if current_user.is_anonymous or current_user.user_type != 'admin':
        flash('You must be an admin to access this page.', 'danger')
        return redirect(url_for('auth.login'))

# Admin Dashboard (Home)
@admin_bp.route('/')
@login_required
def dashboard():
    patients = Patient.query.all()
    doctors = Doctor.query.all()
    return render_template('admin/dashboard.html', patients=patients, doctors=doctors)

# Patients Management
@admin_bp.route('/patients')
@login_required
def patients():
    appointments = Appointment.query.join(Patient).join(Doctor).all()
    return render_template('admin/patients.html', appointments=appointments)

# Update Appointment Status
@admin_bp.route('/appointments/update/<int:appointment_id>/<status>', methods=['POST'])
@login_required
def update_appointment_status(appointment_id, status):
    appointment = Appointment.query.get_or_404(appointment_id)
    
    if status in ['approved', 'rejected', 'pending']:
        appointment.status = status
        
        # If rejected, free up the time slot
        if status == 'rejected':
            time_slot = TimeSlot.query.get(appointment.slot_id)
            if time_slot:
                time_slot.is_booked = False
        
        db.session.commit()
        flash(f'Appointment status updated to {status}.', 'success')
    else:
        flash('Invalid status.', 'danger')
    
    return redirect(url_for('admin.patients'))

# View Patient Details
@admin_bp.route('/patients/view/<int:patient_id>')
@login_required
def view_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    appointments = Appointment.query.filter_by(patient_id=patient_id).join(Doctor).all()
    return render_template('admin/patient_view.html', patient=patient, appointments=appointments)

# Block/Unblock Patient
@admin_bp.route('/patients/toggle_block/<int:patient_id>', methods=['POST'])
@login_required
def toggle_patient_block(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    patient.is_blocked = not patient.is_blocked
    db.session.commit()
    
    status = "blocked" if patient.is_blocked else "unblocked"
    flash(f'Patient {patient.name} has been {status}.', 'success')
    return redirect(url_for('admin.dashboard'))

# Doctors Management
@admin_bp.route('/doctors', methods=['GET', 'POST'])
@login_required
def doctors():
    form = DoctorForm()
    
    if form.validate_on_submit():
        doctor = Doctor(
            name=form.name.data,
            specialization=form.specialization.data,
            fees=form.fees.data,
            address=form.address.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            slot_duration=form.slot_duration.data,
            available_days=form.available_days.data
        )
        
        db.session.add(doctor)
        db.session.commit()
        flash('New doctor added successfully!', 'success')
        return redirect(url_for('admin.doctors'))
    
    doctors = Doctor.query.all()
    return render_template('admin/doctors.html', form=form, doctors=doctors)

# Edit Doctor
@admin_bp.route('/doctors/edit/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
def edit_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    form = DoctorForm(obj=doctor)
    
    if form.validate_on_submit():
        doctor.name = form.name.data
        doctor.specialization = form.specialization.data
        doctor.fees = form.fees.data
        doctor.address = form.address.data
        doctor.start_time = form.start_time.data
        doctor.end_time = form.end_time.data
        doctor.slot_duration = form.slot_duration.data
        doctor.available_days = form.available_days.data
        
        db.session.commit()
        flash('Doctor information updated successfully!', 'success')
        return redirect(url_for('admin.doctors'))
    
    return render_template('admin/doctors.html', form=form, doctors=Doctor.query.all(), edit_mode=True, doctor_id=doctor_id)

# Delete Doctor
@admin_bp.route('/doctors/delete/<int:doctor_id>', methods=['POST'])
@login_required
def delete_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    
    # Check if there are any approved appointments for this doctor
    active_appointments = Appointment.query.filter_by(doctor_id=doctor_id, status='approved').count()
    
    if active_appointments > 0:
        flash(f'Cannot delete doctor. There are {active_appointments} active appointments.', 'danger')
    else:
        db.session.delete(doctor)
        db.session.commit()
        flash('Doctor deleted successfully!', 'success')
    
    return redirect(url_for('admin.doctors'))

# View Doctor Slots
@admin_bp.route('/doctors/slots/<int:doctor_id>')
@login_required
def view_doctor_slots(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    
    # Get date from query param or use today
    selected_date_str = request.args.get('date', datetime.today().strftime('%Y-%m-%d'))
    selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    
    # Generate slots for the selected date if it hasn't been generated yet
    day_name = selected_date.strftime('%A')
    if day_name in doctor.available_days_list:
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
    
    # Fetch all slots for the selected date
    slots = TimeSlot.query.filter_by(doctor_id=doctor_id, date=selected_date).order_by(TimeSlot.start_time).all()
    
    # Get dates for the next week for date selector
    dates = []
    for i in range(7):
        day = datetime.today().date() + timedelta(days=i)
        day_name = day.strftime('%A')
        if day_name in doctor.available_days_list:
            dates.append(day)
    
    return render_template('admin/doctor_slots.html', doctor=doctor, slots=slots, selected_date=selected_date, dates=dates)

# Toggle slot availability
@admin_bp.route('/doctors/slots/toggle/<int:slot_id>', methods=['POST'])
@login_required
def toggle_slot(slot_id):
    slot = TimeSlot.query.get_or_404(slot_id)
    
    # Check if slot already has an appointment
    appointment = Appointment.query.filter_by(slot_id=slot_id).first()
    if appointment and not slot.is_booked:
        flash('Cannot free this slot as it is already booked.', 'danger')
    else:
        slot.is_booked = not slot.is_booked
        db.session.commit()
        status = "reserved" if slot.is_booked else "freed"
        flash(f'Slot has been {status}.', 'success')
    
    return redirect(url_for('admin.view_doctor_slots', doctor_id=slot.doctor_id, date=slot.date))

# Admin Analytics Dashboard
@admin_bp.route('/summary')
@login_required
def summary():
    total_doctors = Doctor.query.count()
    total_patients = Patient.query.count()
    
    # Appointments today
    today = datetime.today().date()
    appointments_today = Appointment.query.filter_by(date=today).count()
    
    # Get appointments count by date for the last 7 days
    last_week = today - timedelta(days=6)
    appointments_by_date = db.session.query(
        Appointment.date, 
        func.count(Appointment.id)
    ).filter(
        Appointment.date >= last_week,
        Appointment.date <= today
    ).group_by(Appointment.date).all()
    
    # Format for chart.js
    dates = [(last_week + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
    appointment_counts = [0] * 7
    
    for app_date, count in appointments_by_date:
        day_diff = (app_date - last_week).days
        if 0 <= day_diff < 7:
            appointment_counts[day_diff] = count
    
    # Get doctor with highest patients
    doctor_stats = db.session.query(
        Doctor.name,
        func.count(Appointment.id).label('appointment_count')
    ).join(Appointment).group_by(Doctor.id).order_by(func.count(Appointment.id).desc()).limit(5).all()
    
    doctor_names = [stat[0] for stat in doctor_stats]
    doctor_counts = [stat[1] for stat in doctor_stats]
    
    return render_template(
        'admin/summary.html', 
        total_doctors=total_doctors,
        total_patients=total_patients,
        appointments_today=appointments_today,
        dates=dates,
        appointment_counts=appointment_counts,
        doctor_names=doctor_names,
        doctor_counts=doctor_counts
    )

# Admin Profile
@admin_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = AdminProfileForm(obj=current_user)
    
    if form.validate_on_submit():
        # Verify current password
        if check_password_hash(current_user.password_hash, form.current_password.data):
            current_user.name = form.name.data
            current_user.email = form.email.data
            
            # Update password if provided
            if form.new_password.data:
                current_user.password_hash = generate_password_hash(form.new_password.data)
            
            db.session.commit()
            flash('Your profile has been updated!', 'success')
            return redirect(url_for('admin.edit_profile'))
        else:
            flash('Current password is incorrect.', 'danger')
    
    return render_template('admin/edit_profile.html', form=form)
