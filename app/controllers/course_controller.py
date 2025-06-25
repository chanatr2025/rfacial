
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from app.models.course import Course
from app.models.user import User
from app.models.course_schedule import CourseSchedule
from app import db, bcrypt
import json

course_bp = Blueprint('courses', __name__, url_prefix='/courses')

@course_bp.route('/')
@login_required
def index():
	search = request.args.get('search', '')
	courses = Course.query.filter(Course.name.ilike(f'%{search}%')).all()
	teachers = User.query.filter(User.role == 'teacher').all()

	return render_template('courses/index.html', courses=courses, teachers=teachers, search=search)

@course_bp.route('/<id>')
@login_required
def getById(id):
	course = Course.query.get(id)

	if not course:
		return jsonify({'error': 'Curso no encontrado'}), 404

	return jsonify({
		'id': course.id,
		'name': course.name,
		'teacher_id': course.teacher_id,
		'teacher': course.teacher.name if course.teacher else None,
		'schedules': [
			{
				'id': schedule.id,
				'day_of_week': schedule.day_name,
				'start_time': schedule.begin_time.strftime('%H:%M'),
				'end_time': schedule.end_time.strftime('%H:%M')
			} for schedule in course.schedules
		]
	})

@course_bp.route('/', methods=['POST'])
@login_required
def create():
	try:
		db.session.begin_nested()
		data = request.form
		if not data or not data.get('name') or not data.get('teacher_id'):
			flash('El nombre y el docente son obligatorios', 'error')
			return redirect(url_for('courses.index'))

		if Course.query.filter_by(name=data.get('name')).first():
			flash('Ya existe un curso con ese nombre', 'error')
			return redirect(url_for('courses.index'))

		course = Course(
			name=data.get('name'),
			teacher_id=data.get('teacher_id')
		)

		db.session.add(course)
		db.session.flush()

		if data.get('schedules'):
			schedules = json.loads(data.get('schedules'))
			for schedule in schedules:
				if schedule.get('day_of_week') and schedule.get('start_time') and schedule.get('end_time'):
					course_schedule = CourseSchedule(
						course_id=course.id,
						day_name=schedule['day_of_week'],
						begin_time=schedule['start_time'],
						end_time=schedule['end_time']
					)
					db.session.add(course_schedule)

		db.session.commit()

		flash('Operación realizada exitosamente', 'success')
		return redirect(url_for('courses.index'))
	except Exception as e:
		print(f"Error al crear curso: {e}")
		db.session.rollback()
		flash('Ocurrió un error, por favor intente nuevamente.', 'error')
		return redirect(url_for('courses.index'))

@course_bp.route('/update/<id>', methods=['POST'])
@login_required
def update(id):
	try:
		data = request.form
		course = Course.query.get(id)

		if not course:
			flash('Curso no encontrado', 'error')
			return redirect(url_for('courses.index'))
		if not data or not data.get('name') or not data.get('teacher_id'):
			flash('El nombre y el docente son obligatorios', 'error')
			return redirect(url_for('courses.index'))
		if course.query.filter(course.name == data.get('name'), course.id != id).first():
			flash('Ya existe un curso con ese nombre', 'error')
			return redirect(url_for('courses.index'))

		course.name = data.get('name')
		course.teacher_id = data.get('teacher_id')

		if data.get('schedules'):
			schedules = json.loads(data.get('schedules'))
			# Eliminar horarios existentes
			for schedule in course.schedules:
				db.session.delete(schedule)
			# Agregar nuevos horarios
			for schedule in schedules:
				if schedule.get('day_of_week') and schedule.get('start_time') and schedule.get('end_time'):
					course_schedule = CourseSchedule(
						course_id=course.id,
						day_name=schedule['day_of_week'],
						begin_time=schedule['start_time'],
						end_time=schedule['end_time']
					)
					db.session.add(course_schedule)

		db.session.commit()
		flash('Operación realizada exitosamente', 'success')
		return redirect(url_for('courses.index'))
	except Exception as e:
		db.session.rollback()
		flash('Ocurrió un error, por favor intente nuevamente.', 'error')
		return redirect(url_for('courses.index'))

@course_bp.route('/delete/<id>', methods=['POST'])
@login_required
def delete(id):
	try:
		course = Course.query.get(id)

		if not course:
			flash('Curso no encontrado', 'error')
			return redirect(url_for('courses.index'))

		db.session.delete(course)
		db.session.commit()

		flash('Operación realizada exitosamente', 'success')
		return redirect(url_for('courses.index'))
	except Exception as e:
		db.session.rollback()
		flash('Ocurrió un error, por favor intente nuevamente.', 'error')
		return redirect(url_for('courses.index'))