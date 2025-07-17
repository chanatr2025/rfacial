
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from app.models.user import User
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.course_schedule import CourseSchedule
from app.models.attendance import Attendance
from app import VIDEO_URL
from datetime import datetime, timedelta
from io import BytesIO
import pandas as pd

admin_bp = Blueprint('admin', __name__)

def parse_date(date_str, end_of_day=False):
	try:
		dt = datetime.strptime(date_str, '%Y-%m-%d')
		if end_of_day:
			dt = dt + timedelta(hours=23, minutes=59, seconds=59, microseconds=999999)
		return dt
	except (ValueError, TypeError):
		return None

@admin_bp.route('/')
@login_required
def home():
	course_id = request.args.get('course', '').strip()
	student_id = request.args.get('student', '').strip()
	begin_date = parse_date(request.args.get('begin_date', ''))
	end_date = parse_date(request.args.get('end_date', ''), end_of_day=True)

	# Filtros comunes
	filter_conditions = []

	if course_id:
		filter_conditions.append(Attendance.course_id == course_id)
	if student_id:
		filter_conditions.append(Attendance.user_id == student_id)
	if begin_date:
		filter_conditions.append(Attendance.register_date >= begin_date)
	if end_date:
		filter_conditions.append(Attendance.register_date <= end_date)

	if current_user.role == 'admin':
		courses = Course.query.all()
		students = User.query.filter_by(role='student').all()
		attendances = Attendance.query.filter(*filter_conditions).all()
		return render_template('dashboard/admin.html', video_url=VIDEO_URL, attendances=attendances, courses=courses, students=students, begin_date=begin_date, end_date=end_date, course_id=course_id, student_id=student_id)
	elif current_user.role == 'student':
		courses = Course.query.join(Enrollment).filter(Enrollment.student_id == current_user.id).all()
		course_ids = [c.id for c in courses]
		filter_conditions.append(Attendance.user_id == current_user.id)
		filter_conditions.append(Attendance.course_id.in_(course_ids))
		attendances = Attendance.query.filter(*filter_conditions).all()
		print(attendances)
		return render_template('dashboard/student.html', courses=courses, attendances=attendances, begin_date=begin_date, end_date=end_date, course_id=course_id)
	elif current_user.role == 'teacher':
		courses = Course.query.filter_by(teacher_id=current_user.id).all()
		course_ids = [c.id for c in courses]
		students = User.query.join(Enrollment).filter(Enrollment.course_id.in_(course_ids), User.role == 'student').all()
		filter_conditions.append(Attendance.user_id.in_([s.id for s in students]))
		filter_conditions.append(Attendance.course_id.in_(course_ids))
		attendances = Attendance.query.filter(*filter_conditions).all()
		print(courses[0].schedules)
		return render_template('dashboard/teacher.html', courses=courses, attendances=attendances, begin_date=begin_date, end_date=end_date, course_id=course_id, students=students, student_id=student_id)

	return render_template('home.html', user=current_user)

@admin_bp.route('/download-attendance')
@login_required
def download_attendance():
	course_id = request.args.get('course', '').strip()
	student_id = request.args.get('student', '').strip()
	begin_date = parse_date(request.args.get('begin_date', ''))
	end_date = parse_date(request.args.get('end_date', ''), end_of_day=True)

	#  data
	data = []

	# Filtros comunes
	filter_conditions = []

	if course_id:
		filter_conditions.append(Attendance.course_id == course_id)
	if student_id:
		filter_conditions.append(Attendance.user_id == student_id)
	if begin_date:
		filter_conditions.append(Attendance.register_date >= begin_date)
	if end_date:
		filter_conditions.append(Attendance.register_date <= end_date)

	if current_user.role == 'admin':
		courses = Course.query.all()
		students = User.query.filter_by(role='student').all()
		data = Attendance.query.filter(*filter_conditions).all()
	elif current_user.role == 'student':
		courses = Course.query.join(Enrollment).filter(Enrollment.student_id == current_user.id).all()
		course_ids = [c.id for c in courses]
		filter_conditions.append(Attendance.user_id == current_user.id)
		filter_conditions.append(Attendance.course_id.in_(course_ids))
		data = Attendance.query.filter(*filter_conditions).all()
	elif current_user.role == 'teacher':
		courses = Course.query.filter_by(teacher_id=current_user.id).all()
		course_ids = [c.id for c in courses]
		students = User.query.join(Enrollment).filter(Enrollment.course_id.in_(course_ids), User.role == 'student').all()
		filter_conditions.append(Attendance.user_id.in_([s.id for s in students]))
		filter_conditions.append(Attendance.course_id.in_(course_ids))
		data = Attendance.query.filter(*filter_conditions).all()

	df = pd.DataFrame([
		{
			'Curso': attendance.course.name if attendance.course else 'No asignado',
			'Docente': attendance.course.teacher.name if attendance.course and attendance.course.teacher else 'No asignado',
			'Estudiante': attendance.user.name if attendance.user else 'No asignado',
			'Fecha': attendance.register_date.strftime('%d/%m/%Y') if attendance.register_date else 'No disponible',
			'Hora': attendance.register_date.strftime('%H:%M') if attendance.register_date else 'No disponible',
			'Estado': 'Ingreso' if attendance.type == 'Ingreso' else 'Salida'
		} for attendance in data
	])
	output = BytesIO()
	df.to_excel(output, index=False, engine='openpyxl')
	output.seek(0)

	return send_file(
		output,
		as_attachment=True,
		download_name=f'attendance_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
		mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
	)

@admin_bp.route('/change-video-url', methods=['POST'])
@login_required
def change_video_url():
	new_url = request.form.get('video_url')
	if current_user.role != 'admin':
		flash('Acción no autorizada', 'error')
		return redirect(url_for('admin.home'))
	global VIDEO_URL
	VIDEO_URL = new_url
	flash('URL de video actualizada exitosamente', 'success')
	return redirect(url_for('admin.home'))