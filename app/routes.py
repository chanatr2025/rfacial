from .controllers import auth_controller, admin_controller, user_controller, course_controller, enrollment_controller, attendance_controller

def register_routes(app):
	app.register_blueprint(auth_controller.auth_bp)
	app.register_blueprint(admin_controller.admin_bp)
	app.register_blueprint(user_controller.user_bp)
	app.register_blueprint(course_controller.course_bp)
	app.register_blueprint(enrollment_controller.enrollment_bp)
	app.register_blueprint(attendance_controller.attendance_bp)