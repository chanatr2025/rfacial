from flask import Blueprint, send_file, Response, jsonify, request
from flask_login import login_required, current_user
from deepface import DeepFace
import cv2
import os
import sys
from datetime import datetime
from app import db
from app.models.user import User
from app.models.course import Course
from app.models.attendance import Attendance
from app.models.enrollment import Enrollment
import pandas as pd
from io import BytesIO

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')
VIDEO_URL = 0

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
		# Convert the frame to RGB format for DeepFace
		frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
		# Save the frame to a temporary file
		temp_frame_path = 'temp_frame.jpg'
		cv2.imwrite(temp_frame_path, frame_rgb)
		# Suppress DeepFace output
		sys.stdout = open(os.devnull, 'w')
		# Perform facial recognition
		results = DeepFace.find(
			img_path=frame,
			db_path='dataset',
			model_name='Facenet512',  # Puedes cambiar el modelo si lo deseas
			enforce_detection=False,
			detector_backend='mtcnn',
			distance_metric='cosine'
		)
		sys.stdout = sys.__stdout__  # Restore standard output

		recognized_people = set()

		if results and len(results) > 0:
			for result in results:
				for _, row in result.iterrows():
					filtered = result[result['distance'] < 0.3]
					if not filtered.empty:
						for _, row in filtered.iterrows():
							identity_path = row['identity']
							user_id = os.path.basename(os.path.dirname(identity_path))
							# check if the user is enrolled in the course
							enrollment = Enrollment.query.filter_by(student_id=user_id, course_id=course.id).first()
							if enrollment:
								recognized_people.add(user_id)
		else:
			return jsonify({'error': 'No se reconoció a nadie'}), 404

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
		return send_file(excel_path, as_attachment=True, download_name=f'attendance_{course_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')
	except Exception as e:
		db.session.rollback()
		print(f"Error al tomar asistencia: {e}")
		return jsonify({'error': f'Error al tomar asistencia'}), 500