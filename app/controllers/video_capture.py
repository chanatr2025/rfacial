from deepface import DeepFace
import cv2
import os
import sys
from datetime import datetime
from app import db
from app.models.user import User
from app.models.course import Course
from app.models.attendance import Attendance

# URL de la cámara IP (modifica según tu configuración)
CAMERA_URL = 0 # "http://192.168.56.37:8080/video"

# Variables de control
cap = None
capture_started = False

def init_camera():
	global cap
	if cap is None or not cap.isOpened():
		cap = cv2.VideoCapture(CAMERA_URL)


def release_camera():
	global cap
	if cap and cap.isOpened():
		cap.release()
		cap = None


def generate_frames():
	global capture_started
	while capture_started:
		success, frame = cap.read()
		if not success:
			break

		try:
			# Convertir el frame a formato adecuado para DeepFace
			frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

			# Terminar la salida estándar para evitar mensajes de DeepFace
			sys.stdout = open(os.devnull, 'w')

			# pasar el frame a DeepFace
			results = DeepFace.find(
				img_path=frame,
				db_path='dataset',
				model_name='Facenet512',  # Puedes cambiar el modelo si lo deseas
				enforce_detection=False,
				detector_backend='mtcnn',
				distance_metric='cosine'
			)
			sys.stdout = sys.__stdout__  # Restaurar la salida estándar

			recognized_people = set()
			# buscar el curso dia => lunes, martes, etc; hora se encuentra entre begin_time y end_time
			course = Course.query.filter(
				Course.day == datetime.utcnow().strftime('%A').lower(),
				Course.begin_time <= datetime.utcnow().time(),
				Course.end_time >= datetime.utcnow().time()
			).first()

			if not course:
				cv2.putText(frame, "No hay curso activo", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)
				ret, buffer = cv2.imencode('.jpg', frame)
				if not ret:
					continue
				frame = buffer.tobytes()
				yield (b'--frame\r\n'
					b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
				continue

			# filtrar los resultados
			if results:
				for result in results:
					for _, row in result.iterrows():
						filtered = result[result['distance'] < 0.3]  # Ajusta el umbral según sea necesario
						if not filtered.empty:
							for _, row in filtered.iterrows():
								identity_path = row['identity']
								user_id = os.path.basename(os.path.dirname(identity_path))
								recognized_people.add(user_id)
								# Buscar usuario en la BD y registrar asistencia
								user = User.query.get(user_id)
								# Si el usuario ya tiene asistencia registrada para el curso activo y es la fecha actual, no registrar de nuevo
								attendance_exists = Attendance.query.filter(
									Attendance.user_id == user.id,
									Attendance.course_id == course.id,
									db.func.date(Attendance.timestamp) == db.func.current_date()
								).first()
								if user and not attendance_exists:
									attendance = Attendance(
										user_id=user.id,
										user_name=user.name,
										course_id=course.id,  # Usar el curso activo
										timestamp=datetime.utcnow()
									)
									print(f"Registro de asistencia para {user.name} en curso {course.name}")
									db.session.add(attendance)
			# Commit de la sesión de la base de datos
			db.session.commit()

			if recognized_people:
				msg = f"Reconocidos: {', '.join(recognized_people)}"
				color = (0, 255, 0)
			else:
				msg = "No se reconoció a nadie"
				color = (0, 0, 255)

			cv2.putText(frame, msg, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)

		except Exception as e:
			error_msg = f"Error: {str(e)}"
			print(error_msg)
			cv2.putText(frame, error_msg, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)

		ret, buffer = cv2.imencode('.jpg', frame)
		if not ret:
			continue
		frame = buffer.tobytes()
		yield (b'--frame\r\n'
			b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


def start_capture():
	global capture_started
	if not capture_started:
		init_camera()
		capture_started = True
	return generate_frames()


def stop_capture():
	global capture_started
	capture_started = False
	release_camera()
	cv2.destroyAllWindows()
