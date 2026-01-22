import cv2
import numpy as np
import onnxruntime
import os
from facenet_pytorch import MTCNN
from PIL import Image

# ---------------- CONFIG ----------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODEL_PATH = os.path.join(BASE_DIR, "dataset", "ds_model.onnx")
KNOWN_FACES_PATH = os.path.join(BASE_DIR, "dataset")
THRESHOLD = 0.5
IMG_SIZE = (112, 112)

# ---------------- MODELO DE EMBEDDINGS ----------------
session = onnxruntime.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])

def preprocess(img):
  """ Preprocesa imagen para el modelo ONNX """
  if img is None:
    raise ValueError("Imagen vacía (NoneType).")
  img = cv2.resize(img, IMG_SIZE)
  img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
  img = img.astype(np.float32)
  img = (img / 255.0 - 0.5) / 0.5   # Normalización a [-1, 1]
  img = np.transpose(img, (2, 0, 1)) # HWC -> CHW
  img = np.expand_dims(img, axis=0)  # batch
  return img

def get_embedding(img):
  preprocessed = preprocess(img)
  inputs = {session.get_inputs()[0].name: preprocessed}
  output = session.run(None, inputs)[0][0]
  return output / np.linalg.norm(output)

def cosine_similarity(a, b):
  return np.dot(a, b)

# ---------------- CARGA DE ROSTROS CONOCIDOS ----------------
def load_known_faces():
  print("Cargando rostros conocidos...")
  known_embeddings = []
  known_names = []

  for person_name in os.listdir(KNOWN_FACES_PATH):
    person_dir = os.path.join(KNOWN_FACES_PATH, person_name)
    if not os.path.isdir(person_dir):
      continue

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

# ---------------- DETECTOR DE ROSTROS (MTCNN) ----------------
mtcnn = MTCNN(keep_all=True, device='cpu')

def recognize_faces(frame):
  """Detecta y reconoce rostros en un frame usando MTCNN + ONNX"""
  image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
  image_pil = Image.fromarray(image_rgb)

  boxes, _ = mtcnn.detect(image_pil)
  if boxes is None:
    return []

  known_embeddings, known_names = load_known_faces()
  if not known_embeddings:
    print("No se encontraron rostros conocidos.")
    return []

  recognized_faces = []

  for box in boxes:
    x1, y1, x2, y2 = [int(b) for b in box]
    face_img = frame[y1:y2, x1:x2]
    if face_img.size == 0:
      continue

    try:
      embedding = get_embedding(face_img)
    except Exception as e:
      print(f"Error en embedding: {e}")
      continue

    best_score = -1
    best_name = None

    for known_embedding, name in zip(known_embeddings, known_names):
      score = cosine_similarity(embedding, known_embedding)
      if score > best_score:
        best_score = score
        best_name = name

    print(f"Reconocido: {best_name} con score {best_score:.2f}")
    if best_score > THRESHOLD:
      recognized_faces.append(best_name)
	  

    # Dibujo en el frame (opcional)
    color = (0, 255, 0) if best_score > THRESHOLD else (0, 0, 255)
    label = best_name if best_score > THRESHOLD else "Desconocido"
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    cv2.putText(frame, f"{label} ({best_score:.2f})", (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

  return recognized_faces