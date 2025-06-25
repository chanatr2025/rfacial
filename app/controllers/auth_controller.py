from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from app import db, bcrypt
from app.models.user import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
	if request.method == 'POST':
		try:
			user = User.query.filter_by(email=request.form.get('email')).first()
			if user and bcrypt.check_password_hash(user.password, request.form.get('password')):
				login_user(user)
				return redirect(url_for('admin.home'))
			else:
				flash('Credenciales inválidas. Inténtalo de nuevo.', 'error')
				return redirect(url_for('auth.login'))
		except Exception as e:
			print(f"Error during login: {e}")
			flash('Ocurrió un error al iniciar sesión. Por favor, inténtalo de nuevo.', 'error')
			return redirect(url_for('auth.login'))
	return render_template('auth/login.html')

""" @auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('email')
        password = bcrypt.generate_password_hash(request.form.get('email')).decode('utf-8')

        if User.query.filter_by(username=username).first():
            flash('El usuario ya existe.')
            return redirect(url_for('auth.register'))

        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        flash('Usuario creado con éxito. Inicia sesión.')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')
 """
@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
