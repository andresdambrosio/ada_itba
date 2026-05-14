# Ada — Agente Académico del ITBA

Asistente conversacional construido con **Google ADK** y **Gemini 2.5 Flash** que responde preguntas sobre carreras del ITBA y gestiona inscripciones a materias.

Desarrollado como proyecto de aprendizaje para el curso de IA Generativa y Agentes del ITBA.

---

## ¿Qué hace Ada?

- Responde preguntas sobre carreras, planes de estudio, admisión y aranceles usando búsqueda semántica (RAG) sobre documentación real del ITBA.
- Permite que alumnos se inscriban en materias con persistencia en SQLite e idempotencia garantizada.
- Escala casos complejos (equivalencias, excepciones) a asesores académicos generando un ticket.
- Habla en español rioplatense, sin inventar información: si no sabe, lo dice.

## Stack

| Capa | Tecnología |
|---|---|
| Orquestación de agente | Google ADK 1.32.0 |
| LLM | Gemini 2.5 Flash |
| Embeddings | gemini-embedding-001 |
| Vector store | ChromaDB (local) |
| Base de datos | SQLite |
| UI | ADK Web (FastAPI) |

## Estructura

```
ada_itba/
├── ingest.py                   # Indexa documentos en ChromaDB (correr una vez)
├── spec.md                     # Especificación técnica del proyecto
└── my_agent/
    ├── agent.py                # Declaración del agente (modelo, tools, safety)
    ├── prompt.py               # System instruction
    ├── tools.py                # 5 herramientas Python para Gemini
    ├── db.py                   # Acceso a SQLite
    └── rag/
        ├── knowledge_base.py   # Motor RAG: indexación y búsqueda semántica
        └── documents/          # Base de conocimiento (.md)
```

## Herramientas disponibles

El agente puede llamar 5 funciones vía function calling:

| Tool | Qué hace |
|---|---|
| `search_knowledge_base(query)` | Busca en ChromaDB y devuelve los 3 chunks más relevantes |
| `enroll_in_subject(student_id, subject_code, subject_name)` | Inscribe al alumno en una materia (con idempotencia en dos capas) |
| `get_my_enrollments(student_id)` | Lista las materias en las que está anotado el alumno |
| `get_subject_enrollments(subject_code)` | Lista los alumnos inscriptos en una materia |
| `escalate_to_academic_advisor(issue_summary, urgency)` | Genera un ticket de soporte para el asesor académico |

## Setup

**Requisitos:** Python 3.11+, una API Key de [Google AI Studio](https://aistudio.google.com/apikey).

```bash
# 1. Instalar dependencias
pip install google-adk chromadb python-dotenv

# 2. Crear archivo de configuración
echo "GOOGLE_API_KEY=tu_key_aqui" > my_agent/.env
echo "GOOGLE_GENAI_USE_VERTEXAI=FALSE" >> my_agent/.env

# 3. Indexar la base de conocimiento (solo la primera vez)
python ingest.py

# 4. Levantar la interfaz web
adk web
```

Abrí el navegador en `http://127.0.0.1:8000`, seleccioná `my_agent` y empezá a chatear.

## Ejemplo de uso

```
Usuario: Hola, quiero inscribirme en Videojuegos. Mi legajo es 39071.

Ada: ¡Hola! Encontré la materia: Videojuegos (INFO-410). ¿Confirmás que querés inscribirte?

Usuario: Sí.

Ada: ¡Listo! Te inscribí en Videojuegos (INFO-410) el 14/05/2026.
     Si necesitás ver todas tus materias, avisame.
```

## Arquitectura

### RAG

`ingest.py` divide los documentos `.md` en chunks de 400 palabras (overlap 50), genera embeddings con `gemini-embedding-001` y los persiste en ChromaDB. En runtime, `knowledge_base.search()` convierte la query en embedding y busca por similitud coseno — devuelve los 3 chunks más cercanos con score de 0 a 1.

### Idempotencia de inscripciones

Dos capas de defensa para evitar duplicados:

1. **Python:** `db.is_enrolled()` verifica antes de insertar y retorna un mensaje amigable si la inscripción ya existe.
2. **SQL:** el constraint `UNIQUE(student_id, subject_code)` en SQLite rechaza el segundo INSERT en caso de concurrencia, y el código captura el `IntegrityError`.

## Limitaciones (scope educativo)

- No hay autenticación: cualquier `student_id` se acepta.
- Las inscripciones persisten en SQLite local, no en el SGA real del ITBA.
- Las sesiones son in-memory: el historial no persiste entre reinicios del servidor.
- La escalada a asesores es un mock: no envía mails reales.

## Archivos que no se suben a git

```
my_agent/.env
my_agent/inscripciones.db
my_agent/.adk/
my_agent/rag/chroma_db/
my_agent/__pycache__/
my_agent/rag/__pycache__/
```
