import cv2
import numpy as np
import onnxruntime
import os

# ---------------- CONFIG ----------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
""" BASE_DIR = os.path.dirname(os.path.abspath(__file__)) """

MODEL_PATH = os.path.join(BASE_DIR, "dataset", "ds_model.onnx")
#tengo almacenado por cada persona una carpeta con sus imágenes
KNOWN_FACES_PATH = os.path.join(BASE_DIR, "dataset")
THRESHOLD = 0.5  # Similitud mínima para aceptar coincidencia
IMG_SIZE = (112, 112)

# ---------------- MODELO ----------------
session = onnxruntime.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])

def preprocess(img):
	img = cv2.resize(img, IMG_SIZE)
	img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
	img = np.transpose(img, (2, 0, 1)).astype(np.float32)
	img = (img - 127.5) / 128.0
	return np.expand_dims(img, axis=0)

def get_embedding(img):
	preprocessed = preprocess(img)
	inputs = {session.get_inputs()[0].name: preprocessed}
	output = session.run(None, inputs)[0][0]
	return output / np.linalg.norm(output)

def cosine_similarity(a, b):
	return np.dot(a, b)

def load_known_faces():
	print("Cargando rostros conocidos...")
	known_embeddings = []
	known_names = []

	for person_name in os.listdir(KNOWN_FACES_PATH):
		person_dir = os.path.join(KNOWN_FACES_PATH, person_name)
		if not os.path.isdir(person_dir):
			continue  # Ignora archivos sueltos

		for filename in os.listdir(person_dir):
			img_path = os.path.join(person_dir, filename)
			img = cv2.imread(img_path)
			if img is None:
				continue

			embedding = get_embedding(img)
			known_embeddings.append(embedding)
			known_names.append(person_name)

	print(f"{len(known_names)} rostros cargados.")
	return known_embeddings, known_names

def recognize_faces(frame):
	face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
	faces = face_cascade.detectMultiScale(frame, scaleFactor=1.3, minNeighbors=5)
	if len(faces) == 0:
		return []

	known_embeddings, known_names = load_known_faces()
	if not known_embeddings or not known_names:
		print("No se encontraron rostros conocidos.")
		return []

	recognized_faces = []
	for (x, y, w, h) in faces:
		face_img = frame[y:y+h, x:x+w]
		if face_img.size == 0:
			continue
		try:
			embedding = get_embedding(face_img)
		except:
			continue

		best_score = -1
		best_name = None

		for known_embedding, name in zip(known_embeddings, known_names):
			score = cosine_similarity(embedding, known_embedding)
			if score > best_score:
				best_score = score
				best_name = name

		print(known_names)
		print(f"Reconocido: {best_name} con score {best_score:.2f}")
		if best_score >= THRESHOLD:
			recognized_faces.append(best_name)
			label = f"{name} ({best_score*100:.2f}%)"
			color= (0, 255, 0)
		else:
			label="Desconocido"
			color=(0,0,255)

        # Dibujar
		cv2.rectangle(frame,(x,y), (x+w, y+h), color, 2)
		cv2.putText(frame,label,(x, y-10),2, 0.7, color, 2, cv2.LINE_AA)

	return recognized_faces