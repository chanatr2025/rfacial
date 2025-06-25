
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from app.models.user import User
from app import db, bcrypt
import numpy as np
import os

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