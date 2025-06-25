from app import db

class Attendance(db.Model):
	id = db.Column(db.String(36), primary_key=True, default=db.func.uuid())
	user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
	user_name = db.Column(db.String(150), nullable=False)
	course_id = db.Column(db.String(36), db.ForeignKey('course.id'), nullable=False)
	register_date = db.Column(db.DateTime(), nullable=False)
	type = db.Column(db.Enum('Ingreso', 'Salida'), nullable=False)

	user = db.relationship("User", back_populates="attendances")
	course = db.relationship("Course", back_populates="attendances")