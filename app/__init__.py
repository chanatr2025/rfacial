import pymysql
pymysql.install_as_MySQLdb()

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from dotenv import load_dotenv
from flask_bcrypt import Bcrypt
from .config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()
# URL de la cámara IP (modifica según tu configuración)
VIDEO_URL = 0 # "http://192.168.56.37:8080/video"
def create_app():
	load_dotenv()

	app = Flask(__name__)
	app.config.from_object(Config)

	db.init_app(app)
	login_manager.init_app(app)
	migrate.init_app(app, db)
	login_manager.login_view = 'auth.login'

	from .routes import register_routes
	register_routes(app)

	return app
