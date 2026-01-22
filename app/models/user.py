from app import db
from flask_login import UserMixin
from app import login_manager

class User(db.Model, UserMixin):
	id = db.Column(db.String(36), primary_key=True, default=db.func.uuid())
	name = db.Column(db.String(150), nullable=False)
	email = db.Column(db.String(150), unique=True, nullable=False)
	student_code = db.Column(db.String(6), nullable=True)
	avatar = db.Column(db.String(200), nullable=True, default='')
	password = db.Column(db.String(200), nullable=False)
	role = db.Column(db.String(50), nullable=False, default='user')

	enrollments = db.relationship("Enrollment", back_populates="student")
	courses = db.relationship("Course", back_populates="teacher")
	attendances = db.relationship("Attendance", back_populates="user")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)