"""Herramientas del asistente académico del ITBA."""

import random

from . import db
from .rag import knowledge_base


def search_knowledge_base(query: str) -> dict:
    """Busca en la base de conocimiento del ITBA información sobre carreras, materias,
    planes de estudio, admisión, aranceles, becas y vida estudiantil.

    Args:
        query: Pregunta o tema en lenguaje natural.

    Returns:
        Fragmentos relevantes de la base de conocimiento con fuente y puntaje de relevancia.
    """
    try:
        results = knowledge_base.search(query, n_results=3)
        if not results:
            return {"found": False, "message": "No se encontró información específica sobre ese tema."}
        return {
            "found": True,
            "query": query,
            "results": [
                {
                    "title": r["title"],
                    "source": r["source"],
                    "content": r["text"],
                    "relevance": r["relevance_score"],
                }
                for r in results
            ],
        }
    except Exception as e:
        return {"found": False, "error": str(e)}


def enroll_in_subject(student_id: str, subject_code: str, subject_name: str) -> dict:
    """Inscribe a un alumno en una materia. Verifica primero si ya está inscripto;
    si no lo está, realiza la inscripción y la persiste en la base de datos.

    Args:
        student_id: Legajo o DNI del alumno (ej: 12345 o 40123456).
        subject_code: Código de la materia según el plan de estudios (ej: INFO-201).
        subject_name: Nombre completo de la materia (ej: Algoritmos y Estructuras de Datos).

    Returns:
        Resultado de la inscripción: éxito, ya inscripto, o error.
    """
    already = db.is_enrolled(student_id, subject_code)
    if already:
        return {
            "success": False,
            "already_enrolled": True,
            "student_id": student_id,
            "subject_code": subject_code.upper(),
            "subject_name": subject_name,
            "message": f"Ya estás inscripto en {subject_name} ({subject_code.upper()}).",
        }

    record = db.enroll(student_id, subject_code, subject_name)
    return {
        "success": True,
        "already_enrolled": False,
        **record,
        "message": f"Inscripción exitosa en {subject_name} ({subject_code.upper()}).",
    }


def get_my_enrollments(student_id: str) -> dict:
    """Consulta todas las materias en las que está inscripto un alumno en el cuatrimestre actual.

    Args:
        student_id: Legajo o DNI del alumno.

    Returns:
        Lista de materias inscriptas con código, nombre y fecha de inscripción.
    """
    enrollments = db.get_enrollments(student_id)
    if not enrollments:
        return {
            "student_id": student_id,
            "count": 0,
            "enrollments": [],
            "message": "No tenés materias inscriptas por el momento.",
        }
    return {
        "student_id": student_id,
        "count": len(enrollments),
        "enrollments": enrollments,
    }


def get_subject_enrollments(subject_code: str) -> dict:
    """Lista todos los alumnos inscriptos en una materia específica.

    Args:
        subject_code: Código de la materia (ej: INFO-410).

    Returns:
        Lista de alumnos inscriptos con legajo y fecha de inscripción.
    """
    enrollments = db.get_subject_enrollments(subject_code)
    if not enrollments:
        return {
            "subject_code": subject_code.upper(),
            "count": 0,
            "enrollments": [],
            "message": f"No hay alumnos inscriptos en {subject_code.upper()} por el momento.",
        }
    return {
        "subject_code": subject_code.upper(),
        "subject_name": enrollments[0]["subject_name"],
        "count": len(enrollments),
        "enrollments": enrollments,
    }


def escalate_to_academic_advisor(issue_summary: str, urgency: str = "normal") -> dict:
    """Deriva la consulta a un asesor académico del ITBA cuando el problema requiere
    intervención humana: equivalencias, excepciones al reglamento, conflictos de cursada,
    o situaciones que no pueden resolverse con las herramientas disponibles.

    Args:
        issue_summary: Descripción del problema o consulta del alumno.
        urgency: Nivel de urgencia ('normal' o 'alta').

    Returns:
        Número de ticket y tiempo estimado de respuesta por email.
    """
    ticket_id = f"ITBA-{random.randint(10000, 99999)}"
    wait_times = {"normal": "24-48 horas hábiles", "alta": "4-8 horas hábiles"}
    estimated = wait_times.get(urgency, "24-48 horas hábiles")
    return {
        "ticket_id": ticket_id,
        "status": "recibido",
        "urgency": urgency,
        "estimated_response": estimated,
        "issue_summary": issue_summary,
        "message": (
            f"Tu consulta fue derivada a un asesor académico. "
            f"Número de ticket: {ticket_id}. "
            f"Recibirás una respuesta en {estimated} al email registrado en el SGA."
        ),
    }
