
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models.user import User
from app.models.course import Course
from app.models.enrollment import Enrollment
from app import db, bcrypt
import numpy as np
import os
import pandas as pd

user_bp = Blueprint('users', __name__, url_prefix='/users')

@user_bp.route('/')
@login_required
def index():
	search = request.args.get('search', '')
	users = User.query.filter(User.name.ilike(f'%{search}%') | User.email.ilike(f'%{search}%')).all()

	return render_template('users/index.html', users=users, search=search)

@user_bp.route('/<id>')
@login_required
def getById(id):
	user = User.query.get(id)

	if not user:
		return jsonify({'error': 'User not found'}), 404

	return jsonify({
		'id': user.id,
		'name': user.name,
		'email': user.email,
		'student_code': user.student_code,
		'avatar': user.avatar,
		'role': user.role
	})

@user_bp.route('/', methods=['POST'])
@login_required
def create():
	try:
		data = request.form
		if not data or not data.get('name') or not data.get('email'):
			flash('El nombre y el correo electrónico son obligatorios', 'error')
			return redirect(url_for('users.index'))

		if User.query.filter_by(email=data.get('email')).first():
			flash('Ya existe un usuario con ese correo electrónico', 'error')
			return redirect(url_for('users.index'))

		password = bcrypt.generate_password_hash(data.get('password', 'root')).decode('utf-8')

		user = User(
			name=data.get('name'),
			email=data.get('email'),
			student_code=data.get('student_code'),
			avatar='',
			role=data.get('role', 'student'),
			password=password
		)

		db.session.add(user)
		db.session.flush()
		# Create a directory for the user if it doesn't exist
		if not os.path.exists(f'dataset/{user.id}'):
			os.makedirs(f'dataset/{user.id}', exist_ok=True)

		if 'image' in request.files:
			images = request.files.getlist('image')
			avatar_paths = []
			for image in images:
				if image and image.filename:
					filename = f"{image.filename}"
					image_path = f'dataset/{user.id}/{filename}'
					# Save the image
					image.save(image_path)
					avatar_paths.append(image_path)
			if avatar_paths and len(avatar_paths) > 0:
				user.avatar = f'dataset/{user.id}'

		db.session.commit()

		flash('Operación realizada exitosamente', 'success')
		return redirect(url_for('users.index'))
	except Exception as e:
		db.session.rollback()
		flash('Ocurrió un error, por favor intente nuevamente.', 'error')
		return redirect(url_for('users.index'))

@user_bp.route('/import', methods=['POST'])
@login_required
def import_users():
	try:
		if 'excel_file' not in request.files:
			flash('Debe seleccionar un archivo Excel.', 'error')
			return redirect(url_for('users.index'))

		excel_file = request.files.get('excel_file')
		if not excel_file or not excel_file.filename:
			flash('Debe seleccionar un archivo Excel.', 'error')
			return redirect(url_for('users.index'))

		filename = excel_file.filename.lower()
		if not (filename.endswith('.xlsx') or filename.endswith('.xls')):
			flash('Formato no válido. Solo se permiten archivos .xlsx o .xls.', 'error')
			return redirect(url_for('users.index'))

		df = pd.read_excel(excel_file)
		if df.empty:
			flash('El archivo Excel está vacío.', 'error')
			return redirect(url_for('users.index'))

		column_map = {str(col).strip().lower(): col for col in df.columns}
		name_col = column_map.get('name') or column_map.get('nombre')
		email_col = column_map.get('email') or column_map.get('correo') or column_map.get('correo electrónico') or column_map.get('correo electronico')
		student_code_col = column_map.get('student_code') or column_map.get('codigo') or column_map.get('código') or column_map.get('codigo estudiante') or column_map.get('código estudiante')
		role_col = column_map.get('role') or column_map.get('rol')

		if not name_col or not email_col:
			flash('El Excel debe incluir las columnas nombre/name y correo/email.', 'error')
			return redirect(url_for('users.index'))

		created = 0
		skipped = 0
		new_users = []
		existing_emails = {email.lower() for (email,) in db.session.query(User.email).all() if email}

		for _, row in df.iterrows():
			name_val = row.get(name_col)
			email_val = row.get(email_col)

			name = '' if pd.isna(name_val) else str(name_val).strip()
			email = '' if pd.isna(email_val) else str(email_val).strip().lower()

			if not name or not email:
				skipped += 1
				continue

			if email in existing_emails:
				skipped += 1
				continue

			student_code = None
			if student_code_col:
				student_code_val = row.get(student_code_col)
				if not pd.isna(student_code_val):
					student_code = str(student_code_val).strip()

			role = 'student'
			if role_col:
				role_val = row.get(role_col)
				if not pd.isna(role_val):
					normalized_role = str(role_val).strip().lower()
					if normalized_role in ('admin', 'teacher', 'student'):
						role = normalized_role

			password = bcrypt.generate_password_hash('root').decode('utf-8')
			new_users.append(User(
				name=name,
				email=email,
				student_code=student_code,
				avatar='',
				role=role,
				password=password
			))
			existing_emails.add(email)
			created += 1

		if not new_users:
			flash('No se importaron usuarios. Verifique que el archivo tenga datos válidos y correos no repetidos.', 'warning')
			return redirect(url_for('users.index'))

		db.session.add_all(new_users)
		db.session.commit()

		flash(f'Importación completada. Creados: {created}. Omitidos: {skipped}.', 'success')
		return redirect(url_for('users.index'))
	except Exception:
		db.session.rollback()
		flash('Ocurrió un error al importar usuarios desde Excel.', 'error')
		return redirect(url_for('users.index'))

@user_bp.route('/update/<id>', methods=['POST'])
@login_required
def update(id):
	try:
		data = request.form
		user = User.query.get(id)

		if not user:
			flash('Usuario no encontrado', 'error')
			return redirect(url_for('users.index'))
		if not data or not data.get('name') or not data.get('email'):
			flash('El nombre y el correo electrónico son obligatorios', 'error')
			return redirect(url_for('users.index'))
		if User.query.filter(User.email == data.get('email'), User.id != id).first():
			flash('Ya existe un usuario con ese correo electrónico', 'error')
			return redirect(url_for('users.index'))
		if data.get('password'):
			password = bcrypt.generate_password_hash(data.get('password')).decode('utf-8')
			user.password = password

		if 'image' in request.files:
			images = request.files.getlist('image')
			if len(images) > 1:
				# remove old images if they exist
				if os.path.exists(f'dataset/{user.id}'):
					for file in os.listdir(f'dataset/{user.id}'):
						file_path = os.path.join(f'dataset/{user.id}', file)
						if os.path.isfile(file_path):
							os.remove(file_path)
				else:
					os.makedirs(f'dataset/{user.id}', exist_ok=True)

				for image in images:
					if image and image.filename:
						filename = f"{image.filename}"
						image_path = f'dataset/{user.id}/{filename}'
						# Save the image
						image.save(image_path)
						user.avatar = image_path

		user.name = data.get('name')
		user.email = data.get('email')
		user.role = data.get('role', 'user')
		user.student_code=data.get('student_code')

		db.session.commit()
		flash('Operación realizada exitosamente', 'success')
		return redirect(url_for('users.index'))
	except Exception as e:
		print(f"Error updating user: {e}")
		db.session.rollback()
		flash('Ocurrió un error, por favor intente nuevamente.', 'error')
		return redirect(url_for('users.index'))

@user_bp.route('/delete/<id>', methods=['POST'])
@login_required
def delete(id):
	try:
		user = User.query.get(id)

		if not user:
			flash('Usuario no encontrado', 'error')
			return redirect(url_for('users.index'))

		db.session.delete(user)
		db.session.commit()

		flash('Operación realizada exitosamente', 'success')
		return redirect(url_for('users.index'))
	except Exception as e:
		db.session.rollback()
		flash('Ocurrió un error, por favor intente nuevamente.', 'error')
		return redirect(url_for('users.index'))

@user_bp.route('/register-student')
@login_required
def register_student():
	if current_user.role not in ('teacher', 'admin'):
		flash('No tiene permisos para acceder a esta página', 'error')
		return redirect(url_for('admin.index'))

	if current_user.role == 'teacher':
		courses = Course.query.filter_by(teacher_id=current_user.id).all()
	else:
		courses = Course.query.all()

	return render_template('users/register_student.html', courses=courses)


@user_bp.route('/register-student', methods=['POST'])
@login_required
def register_student_post():
	if current_user.role not in ('teacher', 'admin'):
		flash('No tiene permisos para realizar esta acción', 'error')
		return redirect(url_for('admin.index'))

	try:
		data = request.form
		if not data.get('name') or not data.get('email'):
			flash('El nombre y el correo electrónico son obligatorios', 'error')
			return redirect(url_for('users.register_student'))

		course_id = data.get('course_id')
		if not course_id:
			flash('Debe seleccionar un curso', 'error')
			return redirect(url_for('users.register_student'))

		if User.query.filter_by(email=data.get('email')).first():
			flash('Ya existe un usuario con ese correo electrónico', 'error')
			return redirect(url_for('users.register_student'))

		password = bcrypt.generate_password_hash(data.get('password', 'root')).decode('utf-8')

		student = User(
			name=data.get('name'),
			email=data.get('email'),
			student_code=data.get('student_code'),
			avatar='',
			role='student',
			password=password
		)

		db.session.add(student)
		db.session.flush()

		if not os.path.exists(f'dataset/{student.id}'):
			os.makedirs(f'dataset/{student.id}', exist_ok=True)

		if 'image' in request.files:
			images = request.files.getlist('image')
			for image in images:
				if image and image.filename:
					image_path = f'dataset/{student.id}/{image.filename}'
					image.save(image_path)
					student.avatar = f'dataset/{student.id}'

		enrollment = Enrollment(
			student_id=student.id,
			course_id=course_id,
			register_date=db.func.now()
		)
		db.session.add(enrollment)
		db.session.commit()

		flash('Estudiante registrado y matriculado exitosamente', 'success')
		return redirect(url_for('users.register_student'))
	except Exception as e:
		db.session.rollback()
		flash('Ocurrió un error, por favor intente nuevamente.', 'error')
		return redirect(url_for('users.register_student'))
	
@user_bp.route('/register-student/import', methods=['POST'])
@login_required
def register_student_import():
	if current_user.role not in ('teacher', 'admin'):
		flash('No tiene permisos para realizar esta acción', 'error')
		return redirect(url_for('admin.index'))

	try:
		course_id = request.form.get('course_id')
		if not course_id:
			flash('Debe seleccionar un curso', 'error')
			return redirect(url_for('users.register_student'))

		if 'excel_file' not in request.files:
			flash('Debe seleccionar un archivo Excel.', 'error')
			return redirect(url_for('users.register_student'))

		excel_file = request.files.get('excel_file')
		if not excel_file or not excel_file.filename:
			flash('Debe seleccionar un archivo Excel.', 'error')
			return redirect(url_for('users.register_student'))

		filename = excel_file.filename.lower()
		if not (filename.endswith('.xlsx') or filename.endswith('.xls')):
			flash('Formato no válido. Solo se permiten archivos .xlsx o .xls.', 'error')
			return redirect(url_for('users.register_student'))

		df = pd.read_excel(excel_file)
		if df.empty:
			flash('El archivo Excel está vacío.', 'error')
			return redirect(url_for('users.register_student'))

		column_map = {str(col).strip().lower(): col for col in df.columns}
		name_col = column_map.get('name') or column_map.get('nombre')
		email_col = column_map.get('email') or column_map.get('correo') or column_map.get('correo electrónico') or column_map.get('correo electronico')
		student_code_col = column_map.get('student_code') or column_map.get('codigo') or column_map.get('código') or column_map.get('codigo estudiante') or column_map.get('código estudiante')

		if not name_col or not email_col:
			flash('El Excel debe incluir las columnas nombre/name y correo/email.', 'error')
			return redirect(url_for('users.register_student'))

		existing_emails = {email.lower() for (email,) in db.session.query(User.email).all() if email}
		created = skipped = already_enrolled = 0

		for _, row in df.iterrows():
			name_val = row.get(name_col)
			email_val = row.get(email_col)
			name = '' if pd.isna(name_val) else str(name_val).strip()
			email = '' if pd.isna(email_val) else str(email_val).strip().lower()

			if not name or not email:
				skipped += 1
				continue

			student_code = None
			if student_code_col:
				sc_val = row.get(student_code_col)
				if not pd.isna(sc_val):
					student_code = str(sc_val).strip()

			if email in existing_emails:
				# Student already exists — enroll if not yet enrolled
				student = User.query.filter_by(email=email).first()
				if student:
					if Enrollment.query.filter_by(course_id=course_id, student_id=student.id).first():
						already_enrolled += 1
					else:
						db.session.add(Enrollment(student_id=student.id, course_id=course_id, register_date=db.func.now()))
						created += 1
				else:
					skipped += 1
				continue

			password = bcrypt.generate_password_hash('root').decode('utf-8')
			student = User(name=name, email=email, student_code=student_code, avatar='', role='student', password=password)
			db.session.add(student)
			db.session.flush()
			os.makedirs(f'dataset/{student.id}', exist_ok=True)
			db.session.add(Enrollment(student_id=student.id, course_id=course_id, register_date=db.func.now()))
			existing_emails.add(email)
			created += 1

		db.session.commit()

		parts = []
		if created:
			parts.append(f'{created} estudiante(s) registrado(s) y matriculado(s)')
		if already_enrolled:
			parts.append(f'{already_enrolled} ya estaban matriculado(s)')
		if skipped:
			parts.append(f'{skipped} omitido(s) por datos inválidos')

		flash('. '.join(parts) + '.' if parts else 'No se procesaron registros.', 'success' if created else 'warning')
		return redirect(url_for('users.register_student'))
	except Exception as e:
		db.session.rollback()
		flash('Ocurrió un error al importar el archivo Excel.', 'error')
		return redirect(url_for('users.register_student'))
	
@user_bp.route('/my-students')
@login_required
def my_students():
	if current_user.role not in ('teacher', 'admin'):
		flash('No tiene permisos para acceder a esta página', 'error')
		return redirect(url_for('admin.index'))

	if current_user.role == 'teacher':
		courses = Course.query.filter_by(teacher_id=current_user.id).all()
	else:
		courses = Course.query.all()

	course_id = request.args.get('course_id', '')
	search = request.args.get('search', '')

	if not course_id and courses:
		course_id = courses[0].id

	enrollments = []
	if course_id:
		query = (
			Enrollment.query
			.join(Enrollment.student)
			.filter(Enrollment.course_id == course_id)
		)
		if search:
			query = query.filter(
				User.name.ilike(f'%{search}%') |
				User.email.ilike(f'%{search}%') |
				User.student_code.ilike(f'%{search}%')
			)
		enrollments = query.all()

	return render_template(
		'users/my_students.html',
		courses=courses,
		enrollments=enrollments,
		course_id=course_id,
		search=search
	)