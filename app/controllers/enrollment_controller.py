
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from app.models.enrollment import Enrollment
from app.models.user import User
from app.models.course import Course
from app import db, bcrypt

enrollment_bp = Blueprint('enrollments', __name__, url_prefix='/enrollments')

@enrollment_bp.route('/')
@login_required
def index():
	search = request.args.get('search', '')
	enrollments = Enrollment.query.join(Enrollment.course).join(Enrollment.student).filter(
		User.name.ilike(f'%{search}%') |
		Course.name.ilike(f'%{search}%')
	).all()

	students = User.query.filter(User.role == 'student').all()
	courses = Course.query.all()

	return render_template('enrollments/index.html', enrollments=enrollments, students=students, courses=courses, search=search)

@enrollment_bp.route('/', methods=['POST'])
@login_required
def create():
	try:
		course_id = request.form.get('course_id')
		student_ids = request.form.getlist('student_id[]')

		if not course_id or not student_ids:
			flash('El curso y al menos un estudiante son obligatorios', 'error')
			return redirect(url_for('enrollments.index'))

		enrolled_count = 0
		already_enrolled = 0

		for student_id in student_ids:
			if Enrollment.query.filter_by(course_id=course_id, student_id=student_id).first():
				already_enrolled += 1
				continue

			enrollment = Enrollment(
				student_id=student_id,
				course_id=course_id,
				register_date=db.func.now()
			)
			db.session.add(enrollment)
			enrolled_count += 1

		db.session.commit()

		if enrolled_count > 0:
			flash(f'Se inscribieron {enrolled_count} estudiante(s) exitosamente', 'success')
		if already_enrolled > 0:
			flash(f'{already_enrolled} estudiante(s) ya estaban inscritos en este curso', 'warning')

		return redirect(url_for('enrollments.index'))
	except Exception as e:
		db.session.rollback()
		flash('Ocurrió un error, por favor intente nuevamente.', 'error')
		return redirect(url_for('enrollments.index'))

@enrollment_bp.route('/delete/<id>', methods=['POST'])
@login_required
def delete(id):
	try:
		enrollment = Enrollment.query.get(id)

		if not enrollment:
			flash('Matrícula no encontrado', 'error')
			return redirect(url_for('enrollments.index'))

		db.session.delete(enrollment)
		db.session.commit()

		flash('Operación realizada exitosamente', 'success')
		return redirect(url_for('enrollments.index'))
	except Exception as e:
		db.session.rollback()
		flash('Ocurrió un error, por favor intente nuevamente.', 'error')
		return redirect(url_for('enrollments.index'))