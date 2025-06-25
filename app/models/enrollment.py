from app import db

class Enrollment(db.Model):
  id = db.Column(db.String(36), primary_key=True, default=db.func.uuid())
  student_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
  course_id = db.Column(db.String(36), db.ForeignKey('course.id'), nullable=True)
  register_date = db.Column(db.DateTime(), nullable=False)

  student = db.relationship("User", back_populates="enrollments")
  course = db.relationship("Course", back_populates="enrollments")