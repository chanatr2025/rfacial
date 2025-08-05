from flask import Blueprint, send_file, Response, jsonify, request
from flask_login import login_required, current_user
import cv2
import os
import sys

import pandas as pd
from io import BytesIO
from app import VIDEO_URL
from app.controllers.arcface_service import recognize_faces
from app import db
from app.models.user import User
from app.models.course import Course
from app.models.attendance import Attendance
from app.models.enrollment import Enrollment
from datetime import datetime

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')
camera_active = False  # Global o en módulo

@attendance_bp.route('/camera_feed')
@login_required
def camera_feed():
	global camera_active
	camera_active = True
	print('por que entra aqui')

	def generate_frames():
		cap = cv2.VideoCapture(VIDEO_URL)
		while camera_active:
			success, frame = cap.read()
			if not success:
				break
			else:
				# Codifica la imagen en formato JPEG
				_, buffer = cv2.imencode('.jpg', frame)
				frame = buffer.tobytes()

			# Devuelve el frame como parte del stream
			yield (b'--frame\r\n'
				b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
		cap.release()

	return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@attendance_bp.route('/stop_camera', methods=['POST'])
@login_required
def stop_camera():
	global camera_active
	camera_active = False
	return jsonify({'message': 'Cámara detenida'}), 200

@attendance_bp.route('/take/<course_id>', methods=['POST'])
@login_required
def take_attendance(course_id):# json request
	if current_user.role != 'teacher':
		jsonify({'error': 'Acceso no autorizado'}), 403

	course = Course.query.get(course_id)

	data = request.get_json()
	if not data or 'state' not in data or data['state'] not in ['Ingreso', 'Salida']:
		return jsonify({'error': 'Estado no proporcionado'}), 400
	# state Ingreso, Salida
	state = data['state']
	if not course or course.teacher_id != current_user.id:
		return jsonify({'error': 'Curso no encontrado o no autorizado'}), 404

	cap = cv2.VideoCapture(VIDEO_URL)
	success, frame = cap.read()
	cap.release()
	if not success:
		return jsonify({'error': 'No se pudo acceder a la cámara'}), 500

	try:
		user_ids = recognize_faces(frame)

		if not user_ids or len(user_ids) == 0:
			return jsonify({'error': 'No se reconoció a nadie'}), 404

		recognized_people = set()

		for user_id in user_ids:
			# check if the user is enrolled in the course
			enrollment = Enrollment.query.filter_by(student_id=user_id, course_id=course.id).first()
			if enrollment:
				recognized_people.add(user_id)

		if not recognized_people or len(recognized_people) == 0:
			return jsonify({'error': 'No se reconoció a nadie en la imagen'}), 404

		# Record attendance for recognized users
		users = User.query.filter(User.id.in_(recognized_people)).all()
		for user in users:
			print(f"Registro de asistencia para: {user.name} ({user.id}) en curso {course.name} ({course.id}) - Estado: {state}")
			attendance = Attendance(user_id=user.id, course_id=course.id, user_name=user.name, register_date=datetime.now(), type=state)
			db.session.add(attendance)
		db.session.flush()

		df = pd.DataFrame([{
			'Estudiante': user.name,
			'Curso': course.name,
			'Fecha y hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			'Tipo': state
		} for user in users])
		# Create a temporary Excel file path
		excel_path = f'temp_attendance.xlsx'
		# Save DataFrame to Excel
		#df.to_excel('app/' + excel_path, index=False)
		output = BytesIO()
		df.to_excel(output, index=False, engine='openpyxl')
		output.seek(0)

		db.session.commit()
		# Send the Excel file as a response
		return send_file(
    	output,
    	as_attachment=True,
  		download_name=f'attendance_{course_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
			mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
	except Exception as e:
		db.session.rollback()
		print(f"Error al tomar asistencia: {e}")
		return jsonify({'error': f'Error al tomar asistencia'}), 500