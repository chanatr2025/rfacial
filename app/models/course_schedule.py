from app import db

class CourseSchedule(db.Model):
  id = db.Column(db.String(36), primary_key=True, default=db.func.uuid())
  course_id = db.Column(db.String(36), db.ForeignKey('course.id'), nullable=True)
  day_name = db.Column(db.String(10), nullable=False)
  begin_time = db.Column(db.Time(), nullable=False)
  end_time = db.Column(db.Time(), nullable=False)

  course = db.relationship("Course", back_populates="schedules")