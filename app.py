from flask import Flask, render_template, jsonify, request, redirect, url_for, session
import mysql.connector
import datetime
from deepface import DeepFace
import cv2
import os
import uuid
from threading import Lock
from functools import wraps
import bcrypt

app = Flask(__name__)
app.secret_key = 'super_secret_key'  # Clave secreta para usar sessions

# Variable global y lock para controlar la finalización de la captura
finalizar_captura = False
finalizar_lock = Lock()

#############################################
# Decorador para Login y Control de Roles
#############################################

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                return "Acceso no autorizado", 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

#############################################
# Funciones de Conexión y Utilidad
#############################################

def conectar_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Sandra123",
        database="asistencia1"
    )

def obtener_cursos():
    """Obtiene la lista de cursos (con teacher_id)"""
    db = conectar_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, course_name, teacher_id FROM Courses")
    cursos = cursor.fetchall()
    cursor.close()
    db.close()
    return cursos

def obtener_estudiantes():
    """Obtiene la lista de usuarios (incluyendo rol)"""
    db = conectar_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, name, role FROM Users")
    estudiantes = cursor.fetchall()
    cursor.close()
    db.close()
    return estudiantes

def obtener_asistencias():
    """Obtiene el historial de asistencias con información del curso y tipo"""
    db = conectar_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT a.name, c.course_name, a.date, a.type 
        FROM attendance a 
        JOIN Courses c ON a.course_id = c.id 
        ORDER BY a.date DESC
    """)
    asistencias = cursor.fetchall()
    cursor.close()
    db.close()
    return asistencias

def timedelta_to_time(td):
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return datetime.time(hour=hours, minute=minutes, second=seconds)

def is_within_schedule(course_id):
    """Valida que la hora actual se encuentre dentro de algún horario asignado para el curso."""
    db = conectar_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT day_of_week, start_time, end_time FROM course_schedules WHERE course_id = %s", 
        (course_id,)
    )
    schedules = cursor.fetchall()
    cursor.close()
    db.close()

    current_day = datetime.datetime.today().strftime('%A')
    current_time = datetime.datetime.now().time()

    for day_of_week, start_time, end_time in schedules:
        if isinstance(start_time, str):
            start_time = datetime.datetime.strptime(start_time, "%H:%M:%S").time()
        elif isinstance(start_time, datetime.timedelta):
            start_time = timedelta_to_time(start_time)
        if isinstance(end_time, str):
            end_time = datetime.datetime.strptime(end_time, "%H:%M:%S").time()
        elif isinstance(end_time, datetime.timedelta):
            end_time = timedelta_to_time(end_time)
        if day_of_week.lower() == current_day.lower():
            if start_time <= current_time <= end_time:
                return True
    return False

def obtener_camara_disponible():
    """Retorna el índice de una cámara disponible (probando índices 0 a 2)"""
    for i in range(3):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            cap.release()
            return i
    return None

def capturar_imagen():
    """Captura una imagen grupal mediante la cámara y permite finalizar la captura desde la web."""
    global finalizar_captura
    cam_index = obtener_camara_disponible()
    if cam_index is None:
        print("⚠️ No se detectó ninguna cámara disponible.")
        return None

    cap = cv2.VideoCapture(cam_index)
    filename = f"static/{uuid.uuid4().hex}.jpg"

    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️ Error al capturar el frame.")
            break

        cv2.imshow("Captura de grupo - Presiona 's' para capturar", frame)
        
        with finalizar_lock:
            if finalizar_captura:
                print("Finalizando captura por solicitud web")
                filename = None
                break

        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            cv2.imwrite(filename, frame)
            print(f"✅ Imagen guardada: {filename}")
            break

    cap.release()
    cv2.destroyAllWindows()

    with finalizar_lock:
        finalizar_captura = False

    return filename if filename and os.path.exists(filename) else None

#############################################
# Endpoints de Autenticación
#############################################

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form.get("name")
        password = request.form.get("password")
        db = conectar_db()
        cursor = db.cursor()
        cursor.execute("SELECT id, name, role, password FROM Users WHERE name = %s", (name,))
        user = cursor.fetchone()
        cursor.close()
        db.close()
        if user and bcrypt.checkpw(password.encode('utf-8'), user[3].encode('utf-8')):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[2]
            if user[2] == "admin":
                return redirect(url_for('admin_dashboard'))
            elif user[2] == "docente":
                return redirect(url_for('docente_dashboard'))
            elif user[2] == "estudiante":
                return redirect(url_for('estudiante_dashboard'))
            else:
                return "Rol desconocido", 403
        else:
            return render_template("login.html", error="Credenciales inválidas")
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

#############################################
# Dashboard de Administrador
#############################################

@app.route('/admin')
@login_required(role="admin")
def admin_dashboard():
    return render_template("admin_dashboard.html")

#############################################
# Dashboard de Docente
#############################################

@app.route('/docente')
@login_required(role="docente")
def docente_dashboard():
    user_id = session.get("user_id")
    db = conectar_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, course_name FROM Courses WHERE teacher_id = %s", (user_id,))
    courses = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template("docente_dashboard.html", courses=courses)

@app.route('/docente/reconocimiento', methods=['POST'])
@login_required(role="docente")
def docente_reconocimiento():
    course_id = request.form.get("course_id")
    attendance_type = request.form.get("attendance_type")
    if not course_id or not attendance_type:
        return jsonify({"mensaje": "Faltan datos de curso o tipo de asistencia."})

    try:
        course_id = int(course_id)
    except:
        return jsonify({"mensaje": "ID de curso inválido."})

    user_id = session.get("user_id")
    db = conectar_db()
    cursor = db.cursor()
    cursor.execute("SELECT teacher_id FROM Courses WHERE id = %s", (course_id,))
    result = cursor.fetchone()
    if not result or result[0] != user_id:
        cursor.close()
        db.close()
        return jsonify({"mensaje": "No tienes permisos para este curso."})

    if not is_within_schedule(course_id):
        cursor.close()
        db.close()
        return jsonify({"mensaje": "Fuera del horario asignado para este curso."})

    imagen_capturada = capturar_imagen()
    if imagen_capturada is None:
        cursor.close()
        db.close()
        return jsonify({"mensaje": "No se pudo capturar imagen o fue cancelada."})

    dataset_path = "dataset"

    try:
        resultados = DeepFace.find(
            img_path=imagen_capturada,
            db_path=dataset_path,
            model_name='Facenet',
            enforce_detection=False,
            detector_backend='opencv',
            distance_metric='cosine'
        )
    except Exception as e:
        os.remove(imagen_capturada)
        cursor.close()
        db.close()
        return jsonify({"mensaje": f"Error al realizar reconocimiento facial: {str(e)}"})

    personas_reconocidas = set()
    for df in resultados:
        for _, row in df.iterrows():
            ruta = row['identity']
            nombre_carpeta = os.path.basename(os.path.dirname(ruta))
            personas_reconocidas.add(nombre_carpeta)

    if not personas_reconocidas:
        os.remove(imagen_capturada)
        cursor.close()
        db.close()
        return jsonify({"mensaje": "❌ No se reconoció a nadie en la imagen."})

    cursor.execute("SELECT name, id FROM Users")
    usuarios = dict(cursor.fetchall())

    registrados = []
    no_matriculados = []

    for nombre in personas_reconocidas:
        uid = usuarios.get(nombre)
        if uid:
            cursor.execute("SELECT * FROM enrollments WHERE user_id = %s AND course_id = %s", (uid, course_id))
            if cursor.fetchone():
                cursor.execute(
                    "INSERT INTO attendance (name, course_id, date, type) VALUES (%s, %s, %s, %s)",
                    (nombre, course_id, datetime.datetime.now(), attendance_type)
                )
                registrados.append(nombre)
            else:
                no_matriculados.append(nombre)
        else:
            no_matriculados.append(nombre)

    db.commit()
    cursor.close()
    db.close()
    os.remove(imagen_capturada)

    mensaje = ""
    if registrados:
        mensaje += f"✅ Asistencia registrada para: {', '.join(registrados)}. "
    if no_matriculados:
        mensaje += f"⚠️ No están matriculados: {', '.join(no_matriculados)}."

    return jsonify({"mensaje": mensaje})


#############################################
# Dashboard de Estudiante
#############################################

@app.route('/estudiante')
@login_required(role="estudiante")
def estudiante_dashboard():
    user_id = session.get("user_id")
    db = conectar_db()
    cursor = db.cursor()
    # Cursos en los que el estudiante está matriculado
    cursor.execute("""
        SELECT c.id, c.course_name 
        FROM enrollments e 
        JOIN Courses c ON e.course_id = c.id 
        WHERE e.user_id = %s
    """, (user_id,))
    cursos = cursor.fetchall()
    # Asistencias registradas para el estudiante (filtrar por nombre)
    cursor.execute("""
        SELECT a.name, c.course_name, a.date, a.type 
        FROM attendance a 
        JOIN Courses c ON a.course_id = c.id 
        WHERE a.name = %s
        ORDER BY a.date DESC
    """, (session.get("username"),))
    asistencias = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template("estudiante_dashboard.html", cursos=cursos, asistencias=asistencias)

#############################################
# Gestión (Admin): Matrículas, Usuarios, Cursos y Horarios
#############################################

@app.route('/matriculas', methods=['GET', 'POST'])
@login_required(role="admin")
def gestionar_matriculas():
    if request.method == 'POST':
        student_id = request.form.get("student_id")
        course_id = request.form.get("course_id")
        if not student_id or not course_id:
            return jsonify({"mensaje": "Faltan datos de estudiante o curso."})
        db = conectar_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM enrollments WHERE user_id = %s AND course_id = %s", (student_id, course_id))
        if cursor.fetchone():
            mensaje = "El estudiante ya está matriculado en este curso."
        else:
            cursor.execute(
                "INSERT INTO enrollments (user_id, course_id, enrollment_date) VALUES (%s, %s, %s)",
                (student_id, course_id, datetime.datetime.now())
            )
            db.commit()
            mensaje = "Estudiante matriculado exitosamente."
        cursor.close()
        db.close()
        return jsonify({"mensaje": mensaje})
    else:
        estudiantes = obtener_estudiantes()
        cursos = obtener_cursos()
        return render_template('matriculas.html', estudiantes=estudiantes, cursos=cursos)

@app.route('/usuarios', methods=['GET', 'POST'])
@login_required(role="admin")
def gestionar_usuarios():
    db = conectar_db()
    cursor = db.cursor()
    if request.method == 'POST':
        nombre = request.form.get("nombre")
        image_path = request.form.get("image_path", "")
        password = request.form.get("password", "")
        role = request.form.get("role", "estudiante")  # Rol por defecto: estudiante
        if not nombre or not password:
            mensaje = "El nombre y la contraseña son obligatorios."
        else:
            # Hash de la contraseña utilizando bcrypt
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute("INSERT INTO Users (name, image_path, password, role) VALUES (%s, %s, %s, %s)", 
                           (nombre, image_path, hashed, role))
            db.commit()
            mensaje = "Usuario agregado exitosamente."
        cursor.close()
        db.close()
        return jsonify({"mensaje": mensaje})
    else:
        cursor.execute("SELECT id, name, image_path, role FROM Users")
        usuarios = cursor.fetchall()
        cursor.close()
        db.close()
        return render_template('usuarios.html', usuarios=usuarios)

@app.route('/cursos', methods=['GET', 'POST'])
@login_required(role="admin")
def gestionar_cursos():
    db = conectar_db()
    cursor = db.cursor()
    if request.method == 'POST':
        course_name = request.form.get("course_name")
        schedule_desc = request.form.get("schedule", "")
        teacher_id = request.form.get("teacher_id")  # Asignar docente
        if not course_name:
            mensaje = "El nombre del curso es obligatorio."
        else:
            cursor.execute("INSERT INTO Courses (course_name, schedule, teacher_id) VALUES (%s, %s, %s)", 
                           (course_name, schedule_desc, teacher_id))
            db.commit()
            mensaje = "Curso agregado exitosamente."
        cursor.close()
        db.close()
        return jsonify({"mensaje": mensaje})
    else:
        cursor.execute("SELECT id, course_name, schedule, teacher_id FROM Courses")
        cursos = cursor.fetchall()
        cursor.execute("SELECT id, name FROM Users WHERE role = 'docente'")
        docentes = cursor.fetchall()
        cursor.close()
        db.close()
        return render_template('cursos.html', cursos=cursos, docentes=docentes)

@app.route('/horarios', methods=['GET', 'POST'])
@login_required(role="admin")
def gestionar_horarios():
    db = conectar_db()
    cursor = db.cursor()
    if request.method == 'POST':
        course_id = request.form.get("course_id")
        day_of_week = request.form.get("day_of_week")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")
        if not (course_id and day_of_week and start_time and end_time):
            mensaje = "Todos los campos son obligatorios."
        else:
            cursor.execute(
                "INSERT INTO course_schedules (course_id, day_of_week, start_time, end_time) VALUES (%s, %s, %s, %s)",
                (course_id, day_of_week, start_time, end_time)
            )
            db.commit()
            mensaje = "Horario agregado exitosamente."
        cursor.close()
        db.close()
        return jsonify({"mensaje": mensaje})
    else:
        cursor.execute("""
            SELECT cs.id, c.course_name, cs.day_of_week, cs.start_time, cs.end_time 
            FROM course_schedules cs 
            JOIN Courses c ON cs.course_id = c.id
        """)
        horarios = cursor.fetchall()
        cursor.execute("SELECT id, course_name FROM Courses")
        cursos = cursor.fetchall()
        cursor.close()
        db.close()
        return render_template('horarios.html', horarios=horarios, cursos=cursos)

#############################################
# Página Principal (por defecto, Admin)
#############################################

@app.route('/')
@login_required()
def index():
    asistencias = obtener_asistencias()
    cursos = obtener_cursos()
    return render_template('index.html', asistencias=asistencias, cursos=cursos)

if __name__ == "__main__":
    app.run(debug=True)
