from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt import encode as jwt_encode, decode, InvalidTokenError, ExpiredSignatureError
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
import secrets
import cx_Oracle

# Initialize FastAPI app
app = FastAPI()
app.title = "Examenes (Universidad del Qundío)"
app.version = "1.0.1"

# Configuración de CORS
origins = [
    "http://localhost",
    "http://localhost:4200",  # URL de tu aplicación Angular
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Security
security = HTTPBearer()
# Database connection
dsn = cx_Oracle.makedsn("localhost", "1521", service_name="ORCL")
connection = cx_Oracle.connect(user="BELSANTO", password="12345")

clave_secreta = secrets.token_hex(16)

# Lista de tokens inválidos
tokens_invalidos = []

# Helper function to get database cursor
def get_cursor():
    return connection.cursor()

# function to get JWT token creation
def create_jwt_token(user_id: int, is_professor: bool):
    payload = {
        'user_id': user_id,
        'is_professor': is_professor,
        'exp': datetime.utcnow() + timedelta(hours=1)  # Token expires in 1 hour
    }
    return jwt_encode(payload, clave_secreta, algorithm='HS256')

# Verificar token
def verificar_token(token: str = Depends(security)):
    try:
        payload = decode(token.credentials, clave_secreta, algorithms=["HS256"])
        usuario_id = payload["user_id"]
        is_professor = payload["is_professor"]
        expiracion_timestamp = payload["exp"]
        expiracion = datetime.fromtimestamp(expiracion_timestamp, tz=timezone.utc)
        if expiracion > datetime.now(timezone.utc) and token.credentials not in tokens_invalidos:
            return usuario_id, is_professor
        else:
            raise HTTPException(status_code=401, detail="Token expirado o inválido")
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

# Login endpoint
@app.post("/login", tags=['Sesion'])
def login(id: int = Body(...), password: str = Body(...), is_professor: int = Body(...)):
    if is_professor not in [0, 1]:
        raise HTTPException(status_code=400, detail="is_professor must be 0 for student or 1 for professor")

    cursor = get_cursor()
    try:
        if is_professor == 1:
            result = cursor.callfunc("LOGIN_PROFESOR", int, [id, password])
        else:
            result = cursor.callfunc("LOGIN_ESTUDIANTE", int, [id, password])

        if result == 1:
            token = create_jwt_token(user_id=id, is_professor=bool(is_professor))
            return {"token": token}
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    finally:
        cursor.close()

# Logout endpoint
@app.post("/logout", tags=['Sesion'])
def logout(token: str = Depends(security)):
    tokens_invalidos.append(token.credentials)
    return {"message": "Logged out successfully"}

# Endpoint de prueba
@app.get("/protected", tags=['home'])
def protected_route(user_info: Tuple[int, bool] = Depends(verificar_token)):
    user_id, is_professor = user_info
    if is_professor:
        return {"message": f"Bienvenido, profesor {user_id}!"}
    else:
        return {"message": f"Bienvenido, estudiante {user_id}!"}

@app.get("/protected", tags=['home'])
def protected_route(user_id: int = Depends(verificar_token)):
    return {"message": f"¡Bienvenido, usuario {user_id}!"}

# Endpoint to fetch questions for an exam
@app.get("/preguntas/{id_examen}", tags=['Preguntas del Examen'])
def get_preguntas(id_examen: int, user_id: int = Depends(verificar_token)):
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT P.*
            FROM "PREGUNTA" P
            JOIN "EXAMEN_PREGUNTA" EP ON P."ID_PREGUNTA" = EP."ID_PREGUNTA"
            WHERE EP."ID_EXAMEN" = :id_examen
        """, id_examen=id_examen)
        result = cursor.fetchall()
        return result

# Endpoint to fetch schedules
@app.get("/horarios", tags=['Horarios disponibles'],)
def get_horarios(user_id: int = Depends(verificar_token), semana: int = None, semestre: str = None):
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT
                H.*,
                CASE
                    WHEN GH."ID_GRUPO" IS NOT NULL THEN 'SI'
                    ELSE 'NO'
                END AS "GRUPO_ASOCIADO",
                CASE
                    WHEN EH."ID_EXAMEN" IS NOT NULL THEN 'SI'
                    ELSE 'NO'
                END AS "EXAMEN_ASOCIADO"
            FROM
                "HORARIO" H
            LEFT JOIN
                "GRUPO_HORARIO" GH ON H."ID_HORARIO" = GH."ID_HORARIO"
            LEFT JOIN
                "EXAMEN_HORARIO" EH ON H."ID_HORARIO" = EH."ID_HORARIO"
            WHERE
                SEMANA = :semana
            AND
                SEMESTRE = :semestre
            ORDER BY
                INDICE_DIA, HORA, SEMESTRE  ASC
        """, {"semana": semana, "semestre": semestre})
        result = cursor.fetchall()
        return result


@app.get("/semestres", tags=['Semestres disponibles'],)
def get_horarios(user_id: int = Depends(verificar_token)):
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT SEMESTRE, count(DISTINCT SEMANA)
            FROM "HORARIO"
            GROUP BY SEMESTRE
            ORDER BY SEMESTRE  ASC
        """)
        result = cursor.fetchall()
        return result

# Endpoint to fetch students for a group
@app.get("/estudiantes/{id_grupo}", tags=['Ver estudiantes por grupo'])
def get_estudiantes(id_grupo: int, user_id: int = Depends(verificar_token)):
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT E.*
            FROM "ESTUDIANTE" E
            JOIN "ESTUDIANTE_GRUPO" EG ON E."ID_ESTUDIANTE" = EG."ID_ESTUDIANTE"
            WHERE EG."ID_GRUPO" = :id_grupo
        """, id_grupo=id_grupo)
        result = cursor.fetchall()
        return result

# Endpoint to fetch student schedules for a group
@app.get("/estudiantes_horarios/{id_grupo}", tags=['Ver el horario de un grupo'])
def get_estudiantes_horarios(id_grupo: int, user_id: int = Depends(verificar_token)):
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT
                H.*,
                CASE
                    WHEN GH."ID_GRUPO" IS NOT NULL THEN 'SI'
                    ELSE 'NO'
                END AS "GRUPO_ASOCIADO",
                CASE
                    WHEN EH."ID_EXAMEN" IS NOT NULL THEN 'SI'
                    ELSE 'NO'
                END AS "EXAMEN_ASOCIADO"
            FROM
                "BELSANTO"."HORARIO" H
            LEFT JOIN
                "BELSANTO"."GRUPO_HORARIO" GH ON H."ID_HORARIO" = GH."ID_HORARIO"
            LEFT JOIN
                "BELSANTO"."EXAMEN_HORARIO" EH ON H."ID_HORARIO" = EH."ID_HORARIO"
            WHERE GH."ID_GRUPO" = :id_grupo
        """, id_grupo=id_grupo)
        result = cursor.fetchall()
        return result

#Banco de preguntas disponibles para un profesor
@app.get("/banco_preguntas/{id_profe}", tags=['Banco Preguntas'])
def get_banco_preguntas(id_profe: int, tema: str = None, user_id: int = Depends(verificar_token)):
    if tema is None:
        tema = "No definido"  # Valor predeterminado si no se proporciona un tema en la URL

    with get_cursor() as cursor:
        cursor.execute("""
            SELECT P.ID_PREGUNTA, P.TEXTO, P.OPCIONES, P.RESPUESTAS_CORRECTAS, P.ID_TIPO, P.TEMA,
                CASE
                    WHEN P.PRIVACIDAD = 0 THEN 'PUBLICA'
                    WHEN P.PRIVACIDAD = 1 THEN 'PRIVADA'
                    ELSE 'DESCONOCIDA'
                END AS PRIVACIDAD
            FROM PREGUNTA P
            INNER JOIN EXAMEN_PREGUNTA EP ON P.ID_PREGUNTA = EP.ID_PREGUNTA
            INNER JOIN EXAMEN E ON EP.ID_EXAMEN = E.ID_EXAMEN
            WHERE (P.TEMA = :tema AND P.PRIVACIDAD = 0)
            OR (P.TEMA = :tema AND E.ID_PROFESOR = :id_profe )
            ORDER BY P.TEXTO
        """, tema=tema, id_profe=id_profe)
        result = cursor.fetchall()
        return result


#Preguntas privadas de un profesor por tema
@app.get("/preguntas_privadas/{id_profe}", tags=['Banco Preguntas'])
def get_banco_preguntas(id_profe: int, tema: str = None, user_id: int = Depends(verificar_token)):
    if tema is None:
        tema = "No definido"  # Valor predeterminado si no se proporciona un tema en la URL

    with get_cursor() as cursor:
        cursor.execute("""
            SELECT P.ID_PREGUNTA, P.TEXTO, P.OPCIONES, P.RESPUESTAS_CORRECTAS, P.ID_TIPO, P.TEMA,
                CASE
                    WHEN P.PRIVACIDAD = 0 THEN 'PUBLICA'
                    WHEN P.PRIVACIDAD = 1 THEN 'PRIVADA'
                    ELSE 'DESCONOCIDA'
                END AS PRIVACIDAD
            FROM PREGUNTA P
            INNER JOIN EXAMEN_PREGUNTA EP ON P.ID_PREGUNTA = EP.ID_PREGUNTA
            INNER JOIN EXAMEN E ON EP.ID_EXAMEN = E.ID_EXAMEN
            WHERE (P.TEMA = :tema AND E.ID_PROFESOR = :id_profe )
            ORDER BY P.TEXTO
        """, tema=tema, id_profe=id_profe)
        result = cursor.fetchall()
        return result

#Todas las preguntas privadas de un profesor
@app.get("/mis_preguntas/{id_profe}", tags=['Banco Preguntas'])
def get_banco_preguntas(id_profe: int, user_id: int = Depends(verificar_token)):

    with get_cursor() as cursor:
        cursor.execute("""
            SELECT P.ID_PREGUNTA, P.TEXTO, P.OPCIONES, P.RESPUESTAS_CORRECTAS, P.ID_TIPO, P.TEMA,
                CASE
                    WHEN P.PRIVACIDAD = 0 THEN 'PUBLICA'
                    WHEN P.PRIVACIDAD = 1 THEN 'PRIVADA'
                    ELSE 'DESCONOCIDA'
                END AS PRIVACIDAD
            FROM PREGUNTA P
            INNER JOIN EXAMEN_PREGUNTA EP ON P.ID_PREGUNTA = EP.ID_PREGUNTA
            INNER JOIN EXAMEN E ON EP.ID_EXAMEN = E.ID_EXAMEN
            WHERE E.ID_PROFESOR = :id_profe
            ORDER BY P.TEXTO
        """, id_profe=id_profe)
        result = cursor.fetchall()
        return result

# Endpoint para almacenar la presentación del examen
@app.post("/almacenar_presentacion_examen/", tags=['Presentación del Examen'])
def almacenar_presentacion_examen(
    p_id_estudiante: int,
    p_id_examen: int,
    p_fecha_presentacion: str,
    p_tiempo_tomado: str,
    p_respuestas: str,  # Movido antes de p_direccion_ip
    p_direccion_ip: str = None,
    user_id: int = Depends(verificar_token)  # Verificar token y obtener user_id
):
    # Verificar que el usuario es un estudiante
    if user_id is None:
        raise HTTPException(status_code=401, detail="Solo los estudiantes pueden presentar un examen")

    try:
        # Llamar a la función PL/SQL para almacenar la presentación del examen
        cursor = get_cursor()
        v_id_presentacion_examen = cursor.callfunc('almacenar_presentacion_examen', int, [
            p_id_estudiante,
            p_id_examen,
            p_fecha_presentacion,
            p_tiempo_tomado,
            p_direccion_ip,
            p_respuestas
        ])
        connection.commit()
        return {"message": "Presentación de examen almacenada correctamente", "id_presentacion_examen": v_id_presentacion_examen}
    except cx_Oracle.Error as error:
        return {"message": f"Error al almacenar la presentación del examen: {error}"}
    finally:
        cursor.close()

# Endpoint para crear un examen
@app.post("/examen/crear", tags=['Exámenes'])
def crear_examen(
    nombre: str = Body(...),
    descripcion: str = Body(...),
    cantidad_preguntas: int = Body(...),
    tiempo_limite: int = Body(...),
    id_curso: int = Body(...),
    id_profesor: int = Body(...),
    user_id: int = Depends(verificar_token)
):
    cursor = get_cursor()
    try:
        result = cursor.callfunc("agregar_examen", int, [nombre, descripcion, cantidad_preguntas, tiempo_limite, id_curso, id_profesor])
        return {"id_examen": result}
    finally:
        cursor.close()

# Endpoint para actualizar un examen
@app.put("/examen/actualizar", tags=['Exámenes'])
def actualizar_examen(
    id_examen: int = Body(...),
    nombre: str = Body(...),
    descripcion: str = Body(...),
    cantidad_preguntas: int = Body(...),
    tiempo_limite: int = Body(...),
    id_curso: int = Body(...),
    id_profesor: int = Body(...),
    user_id: int = Depends(verificar_token)
):
    cursor = get_cursor()
    try:
        result = cursor.callfunc("actualizar_examen", int, [id_examen, nombre, descripcion, cantidad_preguntas, tiempo_limite, id_curso, id_profesor])
        return {"filas_afectadas": result}
    finally:
        cursor.close()

# Endpoint para eliminar un examen
@app.delete("/examen/eliminar", tags=['Exámenes'])
def eliminar_examen(
    id_examen: int = Body(...),
    user_id: int = Depends(verificar_token)
):
    cursor = get_cursor()
    try:
        result = cursor.callfunc("eliminar_examen", int, [id_examen])
        if result == 0:
            raise HTTPException(status_code=400, detail="El examen no se puede eliminar porque está asignado a un horario")
        else:
            return {"mensaje": "Examen eliminado exitosamente"}
    finally:
        cursor.close()

# Endpoint para crear una nueva pregunta
@app.post("/preguntas/crear", tags=['Preguntas'])
def crear_pregunta(
    texto: str = Body(...),
    opciones: str = Body(...),
    respuestas_correctas: str = Body(...),
    id_tipo: int = Body(...),
    tema: str = Body(None),
    privacidad: int = Body(0),
    id_examen: int = Body(...), user_id: int = Depends(verificar_token)
):
    cursor = get_cursor()
    try:
        id_pregunta = cursor.callfunc("insertar_pregunta", int, [texto, opciones, respuestas_correctas, id_tipo, tema, privacidad])
        cursor.execute("INSERT INTO EXAMEN_PREGUNTA (ID_EXAMEN, ID_PREGUNTA) VALUES (:id_examen, :id_pregunta)", id_examen=id_examen, id_pregunta=id_pregunta)
        connection.commit()
        return {"message": "Pregunta agregada exitosamente"}
    finally:
        cursor.close()

# Endpoint para actualizar una pregunta
@app.put("/preguntas/actualizar/{id_pregunta}", tags=['Preguntas'])
def actualizar_pregunta(
    id_pregunta: int,
    texto: str = Body(...),
    opciones: str = Body(...),
    respuestas_correctas: str = Body(...),
    id_tipo: int = Body(...),
    tema: str = Body(None),
    privacidad: int = Body(0), user_id: int = Depends(verificar_token)
):
    cursor = get_cursor()
    try:
        cursor.callfunc("actualizar_pregunta", int, [id_pregunta, texto, opciones, respuestas_correctas, id_tipo, tema, privacidad])
        connection.commit()
        return {"message": "Pregunta actualizada exitosamente"}
    finally:
        cursor.close()

# Endpoint para actualizar la privacidad de una pregunta
@app.put("/preguntas/actualizar-privacidad/{id_pregunta}", tags=['Preguntas'])
def actualizar_privacidad_pregunta(id_pregunta: int, id_profesor: int, privacidad: int, user_id: int = Depends(verificar_token)):
    cursor = get_cursor()
    try:
        result = cursor.callfunc("actualizar_privacidad_pregunta", int, [id_pregunta, id_profesor, privacidad])
        if result == 1:
            connection.commit()
            return {"message": "Privacidad de la pregunta actualizada exitosamente"}
        else:
            return {"message": "No se puede cambiar la privacidad de la pregunta"}
    finally:
        cursor.close()

# Endpoint para eliminar una pregunta
@app.delete("/preguntas/eliminar/{id_pregunta}", tags=['Preguntas'])
def eliminar_pregunta(id_pregunta: int, user_id: int = Depends(verificar_token)):
    cursor = get_cursor()
    try:
        result = cursor.callfunc("eliminar_pregunta", int, [id_pregunta])
        if result == 1:
            connection.commit()
            return {"message": "Pregunta eliminada exitosamente"}
        else:
            return {"message": "No se puede eliminar la pregunta porque está asignada a uno o más exámenes"}
    finally:
        cursor.close()

# Endpoint para crear un estudiante
@app.post("/estudiantes/crear", tags=['Estudiantes'])
def crear_estudiante(
    cedula: int = Body(...),
    p_nombre: str = Body(...),
    clave: str = Body(...), user_id: int = Depends(verificar_token)
):
    cursor = get_cursor()
    try:
        result = cursor.callfunc("CREAR_ESTUDIANTE", bool, [cedula, p_nombre, clave])
        if result:
            connection.commit()
            return {"message": "Estudiante creado exitosamente"}
        else:
            return {"message": "Ya existe un estudiante con la cédula proporcionada"}
    finally:
        cursor.close()

# Endpoint para actualizar un estudiante
@app.put("/estudiantes/actualizar/{cedula}", tags=['Estudiantes'])
def actualizar_estudiante(
    cedula: int,
    p_nombre: str = Body(...),
    clave: str = Body(...), user_id: int = Depends(verificar_token)
):
    cursor = get_cursor()
    try:
        result = cursor.callfunc("ACTUALIZAR_ESTUDIANTE", bool, [cedula, p_nombre, clave])
        if result:
            connection.commit()
            return {"message": "Estudiante actualizado exitosamente"}
        else:
            return {"message": "No se encontró el estudiante con la cédula proporcionada"}
    finally:
        cursor.close()

# Endpoint para eliminar un estudiante
@app.delete("/estudiantes/eliminar/{cedula}", tags=['Estudiantes'])
def eliminar_estudiante(
    cedula: int,
    user_id: int = Depends(verificar_token)
):
    cursor = get_cursor()
    try:
        result = cursor.callfunc("ELIMINAR_ESTUDIANTE", bool, [cedula])
        if result:
            connection.commit()
            return {"message": "Estudiante eliminado exitosamente"}
        else:
            return {"message": "No se encontró el estudiante con la cédula proporcionada"}
    finally:
        cursor.close()

# Endpoint para crear un grupo
@app.post("/grupos/crear", tags=['Grupos'])
def crear_grupo(
    grupo: int = Body(...),
    nombre_grupo: str = Body(...),
    user_id: int = Depends(verificar_token)
):
    cursor = get_cursor()
    try:
        result = cursor.callfunc("CREAR_GRUPO", bool, [grupo, nombre_grupo])
        if result:
            connection.commit()
            return {"message": "Grupo creado exitosamente"}
        else:
            return {"message": "Ya existe un grupo con el ID proporcionado"}
    finally:
        cursor.close()

# Endpoint para crear estudiantes a un grupo
@app.post("/grupos/crear_estudiantes", tags=['Grupos'])
def crear_estudiantes_a_grupo(
    grupo_id: int,
    estudiante_ids: List[int],
    user_id: int = Depends(verificar_token)
):
    cursor = get_cursor()
    try:
        estudiantes_no_agregados = []
        for estudiante_id in estudiante_ids:
            result = cursor.callfunc("crear_ESTUDIANTES_GRUPO", str, [estudiante_id, grupo_id])
            if result != 'Estudiante Agregado':
                estudiantes_no_agregados.append(f"ID Estudiante: {estudiante_id} - {result}")

        if len(estudiantes_no_agregados) == 0:
            connection.commit()
            return {"message": "Todos los estudiantes fueron agregados correctamente"}
        else:
            return {"message": "Algunos estudiantes no pudieron ser agregados", "estudiantes_no_agregados": estudiantes_no_agregados}
    finally:
        cursor.close()

# Endpoint para crear estudiante a un grupo
@app.post("/grupos/crear-estudiante", tags=['Grupos'])
def crear_estudiantes_grupo(
    estudiante_id: int = Body(...),
    grupo_id: int = Body(...), user_id: int = Depends(verificar_token)
):
    cursor = get_cursor()
    try:
        message = cursor.callfunc("crear_ESTUDIANTES_GRUPO", str, [estudiante_id, grupo_id])
        connection.commit()
        return {"message": message}
    finally:
        cursor.close()

# Endpoint para actualizar un grupo
@app.put("/grupos/actualizar/{grupo}", tags=['Grupos'])
def actualizar_grupo(
    grupo: int,
    nombre_grupo: str = Body(...), user_id: int = Depends(verificar_token)
):
    cursor = get_cursor()
    try:
        result = cursor.callfunc("ACTUALIZAR_GRUPO", bool, [grupo, nombre_grupo])
        if result:
            connection.commit()
            return {"message": "Grupo actualizado exitosamente"}
        else:
            return {"message": "No se encontró el grupo con el ID proporcionado"}
    finally:
        cursor.close()

# Endpoint para eliminar un grupo
@app.delete("/grupos/eliminar/{grupo}", tags=['Grupos'])
def eliminar_grupo(
    grupo: int,
    user_id: int = Depends(verificar_token)
):
    cursor = get_cursor()
    try:
        result = cursor.callfunc("ELIMINAR_GRUPO", bool, [grupo])
        if result:
            connection.commit()
            return {"message": "Grupo eliminado exitosamente"}
        else:
            return {"message": "No se encontró el grupo con el ID proporcionado"}
    finally:
        cursor.close()

# Endpoint para crear un profesor
@app.post("/profesores/crear", tags=['Profesores'])
def crear_profesor(
    cedula: int = Body(...),
    p_nombre: str = Body(...),
    clave: str = Body(...),
    user_id: int = Depends(verificar_token)
):
    cursor = get_cursor()
    try:
        result = cursor.callfunc("CREAR_PROFESOR", bool, [cedula, p_nombre, clave])
        if result:
            connection.commit()
            return {"message": "Profesor creado exitosamente"}
        else:
            return {"message": "Ya existe un profesor con la cédula proporcionada"}
    finally:
        cursor.close()

# Endpoint para actualizar un profesor
@app.put("/profesores/actualizar/{cedula}", tags=['Profesores'])
def actualizar_profesor(
    cedula: int,
    p_nombre: str = Body(...),
    clave: str = Body(...), user_id: int = Depends(verificar_token)
):
    cursor = get_cursor()
    try:
        result = cursor.callfunc("ACTUALIZAR_PROFESOR", bool, [cedula, p_nombre, clave])
        if result:
            connection.commit()
            return {"message": "Profesor actualizado exitosamente"}
        else:
            return {"message": "No se encontró el profesor con la cédula proporcionada"}
    finally:
        cursor.close()

# Endpoint para eliminar un profesor
@app.delete("/profesores/eliminar/{cedula}", tags=['Profesores'])
def eliminar_profesor(
    cedula: int,
    user_id: int = Depends(verificar_token)
):
    cursor = get_cursor()
    try:
        result = cursor.callfunc("ELIMINAR_PROFESOR", bool, [cedula])
        if result:
            connection.commit()
            return {"message": "Profesor eliminado exitosamente"}
        else:
            return {"message": "No se encontró el profesor con la cédula proporcionada"}
    finally:
        cursor.close()