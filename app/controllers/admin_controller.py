
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.course_schedule import CourseSchedule
from app.models.attendance import Attendance
from app import VIDEO_URL

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/')
@login_required
def home():
	if current_user.role == 'admin':
		attendances = Attendance.query.all()
		return render_template('dashboard/admin.html', video_url=VIDEO_URL, attendances=attendances)
	elif current_user.role == 'student':
		courses = Course.query.join(Enrollment).filter(Enrollment.student_id == current_user.id).all()
		attendances = Attendance.query.filter(Attendance.user_id == current_user.id).all()
		print(attendances)
		return render_template('dashboard/student.html', courses=courses, attendances=attendances)
	elif current_user.role == 'teacher':
		courses = Course.query.filter(Course.teacher_id == current_user.id).all()
		attendances = Attendance.query.filter(Attendance.course_id.in_([course.id for course in courses])).all()
		print(courses[0].schedules)
		return render_template('dashboard/teacher.html', courses=courses, attendances=attendances)

	return render_template('home.html', user=current_user)

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