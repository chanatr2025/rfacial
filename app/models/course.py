from app import db

class Course(db.Model):
	id = db.Column(db.String(36), primary_key=True, default=db.func.uuid())
	name = db.Column(db.String(150), nullable=False)
	teacher_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)

	enrollments = db.relationship("Enrollment", back_populates="course")
	attendances = db.relationship("Attendance", back_populates="course")
	schedules = db.relationship("CourseSchedule", back_populates="course")

	teacher = db.relationship("User", back_populates="courses")