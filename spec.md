# Spec: Ada — Agente Académico del ITBA

> Asistente virtual conversacional construido con **Google ADK** y **Gemini 2.5 Flash** para responder consultas académicas y gestionar inscripciones a materias del Instituto Tecnológico de Buenos Aires.

---

## 1. Resumen ejecutivo

**Ada** es un agente de IA conversacional para alumnos y aspirantes del ITBA. Responde preguntas sobre carreras, planes de estudio, admisión y aranceles consultando una base de conocimiento RAG, y permite **inscribirse en materias** persistiendo las operaciones en una base de datos SQLite.

Este proyecto nace del refactor de un agente previo de atención al cliente de Mercado Libre. Se conservaron las decisiones de arquitectura (ADK + RAG con ChromaDB) y se reemplazaron tools, prompt y base de conocimiento por equivalentes del dominio universitario.

**Stack:**
- Google ADK 1.32.0 (Python)
- Gemini 2.5 Flash (LLM)
- gemini-embedding-001 (embeddings)
- ChromaDB (vector store local)
- SQLite (persistencia de inscripciones)

---

## 2. Objetivos y no-objetivos

### 2.1 Objetivos

- ✅ Responder preguntas en español argentino sobre carreras del ITBA usando información verificable (RAG sobre planes de estudio reales).
- ✅ Permitir inscripciones a materias con persistencia real (no mocks).
- ✅ Garantizar idempotencia en las inscripciones (defensa en dos capas: chequeo Python + constraint SQL).
- ✅ Demostrar de forma didáctica todos los componentes (presentación + guía HTML) para usar como material educativo.
- ✅ Mantener arquitectura modular para poder reemplazar las capas (ej: SQLite → Postgres, RAG local → API real del ITBA) con mínimo impacto.

### 2.2 No-objetivos (por ahora)

- ❌ Autenticación de alumnos: cualquier `student_id` se acepta sin validar.
- ❌ Integración con el SGA real del ITBA: las inscripciones viven solo en la DB local del proyecto.
- ❌ Multi-turno con estado persistido entre sesiones: ADK usa sesiones in-memory.
- ❌ UI propia: se usa la UI web de ADK (`adk web`).
- ❌ Deploy productivo: el proyecto corre solo en `localhost:8000`.

---

## 3. Arquitectura

```
                            ┌─────────────────────────────┐
                            │  Usuario (browser :8000)    │
                            └──────────────┬──────────────┘
                                           │
                            ┌──────────────▼──────────────┐
                            │      ADK Web Server         │
                            │      (FastAPI + UI)         │
                            └──────────────┬──────────────┘
                                           │
                            ┌──────────────▼──────────────┐
                            │     ADK Orchestrator        │
                            │  session + tool loop        │
                            └──────────────┬──────────────┘
                                           │ ↕
                            ┌──────────────▼──────────────┐
                            │     Gemini 2.5 Flash        │
                            │  (function calling)         │
                            └──────────────┬──────────────┘
                                           │ tool calls
                            ┌──────────────▼──────────────┐
                            │    my_agent/tools.py        │
                            │  5 funciones Python         │
                            └──────┬──────────────┬───────┘
                                   │              │
                  ┌────────────────▼──┐      ┌────▼────────────────┐
                  │  rag/knowledge_   │      │       db.py         │
                  │  base.py          │      │  (acceso a SQLite)  │
                  └─────────┬─────────┘      └──────────┬──────────┘
                            │                           │
                  ┌─────────▼─────────┐      ┌──────────▼──────────┐
                  │  ChromaDB (local) │      │   inscripciones.db  │
                  │  embeddings: 3072d│      │   tabla: inscripcs. │
                  └───────────────────┘      └─────────────────────┘
```

### 3.1 Capas

| Capa | Responsabilidad | Archivos |
|---|---|---|
| **Presentación** | Web UI provista por ADK | (managed) |
| **Orquestación** | Loop LLM ↔ tools, sessions | (managed by ADK) |
| **Agente** | Configuración del agente (modelo, prompt, tools) | `agent.py` |
| **Prompt** | Personalidad, reglas, guardrails | `prompt.py` |
| **Lógica de negocio** | Validaciones, formato de respuestas | `tools.py` |
| **Acceso a datos** | SQL crudo, RAG | `db.py`, `rag/knowledge_base.py` |
| **Persistencia** | Base de datos | SQLite, ChromaDB |

---

## 4. Componentes

### 4.1 `agent.py` — declaración del agente

Define un único `root_agent` (nombre requerido por ADK) con:

- **Modelo:** `gemini-2.5-flash`
- **Nombre:** `itba_academic_assistant`
- **Instruction:** importada desde `prompt.py`
- **Tools:** las 5 funciones de `tools.py`
- **SafetySettings:** los 4 harm categories con `BLOCK_ONLY_HIGH`

### 4.2 `prompt.py` — system prompt de Ada

String multilínea que define:

- **Identidad:** "Ada", asistente académico del ITBA, español argentino (vos/sos/tenés).
- **Flujo de atención:** saludo opcional, identificación (legajo), consulta o inscripción, escalamiento.
- **Reglas críticas:**
  - Nunca inventar códigos de materias → siempre buscar en el RAG primero.
  - Nunca inscribir sin legajo, código y nombre confirmados.
  - Para inscripciones que solo mencionan nombre → buscar el código antes.
- **Tabla de tools** con criterio de cuándo usar cada una.

### 4.3 `tools.py` — las 5 herramientas

Funciones Python con docstring y type hints. ADK las convierte automáticamente en JSON schemas para el LLM.

#### 4.3.1 `search_knowledge_base(query: str) → dict`
Búsqueda semántica en ChromaDB. Devuelve los 3 chunks más relevantes con `title`, `source`, `content` y `relevance_score`. Lectura, sin efectos.

#### 4.3.2 `enroll_in_subject(student_id: str, subject_code: str, subject_name: str) → dict`
1. Verifica con `db.is_enrolled()` si el alumno ya está anotado.
2. Si lo está: devuelve `{success: False, already_enrolled: True, message: "Ya estás inscripto..."}`.
3. Si no lo está: `db.enroll()` persiste el registro y devuelve `{success: True, ...}`.

#### 4.3.3 `get_my_enrollments(student_id: str) → dict`
Devuelve todas las materias del alumno con código, nombre y fecha de inscripción. Si no tiene ninguna: `{count: 0, message: "No tenés materias inscriptas..."}`.

#### 4.3.4 `get_subject_enrollments(subject_code: str) → dict`
Devuelve todos los alumnos inscriptos en una materia. Útil para roles administrativos.

#### 4.3.5 `escalate_to_academic_advisor(issue_summary: str, urgency: str = "normal") → dict`
Genera un ticket `ITBA-XXXXX` y devuelve un tiempo estimado de respuesta (`normal: 24-48hs`, `alta: 4-8hs`). Mock — no envía mail real.

### 4.4 `db.py` — capa de acceso a SQLite

Encapsula todo el SQL. Funciones públicas:

| Función | Operación SQL |
|---|---|
| `is_enrolled(student_id, code) → bool` | `SELECT 1 ... WHERE student_id=? AND subject_code=?` |
| `enroll(student_id, code, name) → dict` | `INSERT INTO inscripciones (...)` con timestamp ISO |
| `get_enrollments(student_id) → list[dict]` | `SELECT * WHERE student_id=? ORDER BY inscripto_en` |
| `get_subject_enrollments(code) → list[dict]` | `SELECT * WHERE subject_code=? ORDER BY inscripto_en` |

**Detalles de diseño:**
- Placeholders parametrizados (`?`) → previene SQL injection.
- `subject_code.upper()` antes de tocar la DB → normalización (no diferencia `INFO-201` vs `info-201`).
- `_init_db()` se llama en cada operación → crea la tabla lazily si no existe (sin script de migración).
- Context manager (`with`) para conexiones → cierre garantizado.

### 4.5 `rag/knowledge_base.py` — motor RAG

#### Indexación (offline, `python ingest.py`)
1. Lee los 5 `.md` de `rag/documents/`.
2. Chunking: 400 palabras por chunk con 50 de overlap.
3. Genera embeddings con `gemini-embedding-001` (`task_type=RETRIEVAL_DOCUMENT`).
4. Persiste vectores + texto + metadata en ChromaDB (colección `itba_knowledge`).

#### Búsqueda (runtime, `knowledge_base.search()`)
1. Genera embedding de la query (`task_type=RETRIEVAL_QUERY`).
2. ChromaDB calcula similitud coseno con todos los vectores.
3. Devuelve top-3 con `relevance_score = 1 - distance`.

**Métrica:** similitud coseno (`hnsw:space=cosine`). Elegida porque captura semejanza semántica independiente de la magnitud del vector (textos cortos vs largos del mismo concepto).

---

## 5. Modelo de datos

### 5.1 Tabla `inscripciones` (SQLite)

```sql
CREATE TABLE IF NOT EXISTS inscripciones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    subject_code    TEXT NOT NULL,
    subject_name    TEXT NOT NULL,
    inscripto_en    TEXT NOT NULL,           -- ISO 8601 string
    UNIQUE(student_id, subject_code)
);
```

**Constraint clave:** `UNIQUE(student_id, subject_code)` garantiza idempotencia a nivel de DB incluso ante race conditions.

Path del archivo: `my_agent/inscripciones.db` (autogenerado al primer uso).

### 5.2 Colección `itba_knowledge` (ChromaDB)

Path: `my_agent/rag/chroma_db/` (sqlite-backed).

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | string | `chunk_0`, `chunk_1`, ... |
| `document` | string | texto del chunk |
| `embedding` | float[3072] | vector de `gemini-embedding-001` |
| `metadata.source` | string | nombre del archivo (sin extensión) |
| `metadata.title` | string | primer encabezado markdown del chunk |

**Configuración:** `hnsw:space = "cosine"`.

**Tamaño actual:** 10 chunks indexados sobre 5 documentos.

---

## 6. Base de conocimiento

Cinco documentos Markdown en `my_agent/rag/documents/`:

| Archivo | Contenido |
|---|---|
| `carreras_overview.md` | Resumen de las 6 carreras del ITBA: INF, IND, ELE, MEC, PET, ANE. Duración, modalidad, posgrados, intercambios. |
| `ingenieria_informatica.md` | Plan completo de Ingeniería en Informática (5 años, 30+ materias con códigos `INFO-XXX`). Correlatividades clave, electivas, salidas laborales. |
| `ingenieria_industrial.md` | Plan completo de Ingeniería Industrial (códigos `INDU-XXX`). Investigación operativa, gestión, electivas. |
| `ingenieria_electronica.md` | Plan completo de Ingeniería Electrónica (códigos `ELEC-XXX`). Laboratorios disponibles, electivas en IoT, 5G, bioelectrónica. |
| `admision_y_aranceles.md` | Curso de Nivelación, aranceles por año, becas, financiamiento, contacto. |

---

## 7. Configuración y secretos

### 7.1 API Key de Google

Una única `GOOGLE_API_KEY` sirve para:
- Llamadas a `gemini-2.5-flash` (vía ADK).
- Llamadas a `gemini-embedding-001` (vía `knowledge_base.py` y `ingest.py`).

**Origen:** [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — tier gratuito alcanza para desarrollo.

**Path del archivo:** `my_agent/.env`

```bash
GOOGLE_API_KEY=AIzaSy...
GOOGLE_GENAI_USE_VERTEXAI=FALSE
```

### 7.2 Cómo cada componente lee la key

| Componente | Mecanismo |
|---|---|
| ADK (`adk web`) | Auto-detecta `.env` adyacente al agente |
| `rag/knowledge_base.py` | `os.environ.get("GOOGLE_API_KEY")` |
| `ingest.py` | `load_dotenv()` explícito vía `python-dotenv` |

### 7.3 Seguridad

- `.env` **NUNCA** se commitea (debe estar en `.gitignore`).
- En su lugar se commitea `.env.example` con la lista de variables sin valores reales.
- Si una key se filtra a un repo público: revocar en AI Studio + generar nueva.
- Producción: usar Secret Manager (AWS/GCP), nunca `.env` files.

---

## 8. Setup y ejecución

### 8.1 Pre-requisitos

- Python 3.12+
- API key de Google AI Studio
- Dependencias instaladas: `google-adk`, `google-genai`, `chromadb`, `python-dotenv`

### 8.2 Pasos

```bash
# 1. Configurar la API key
echo "GOOGLE_API_KEY=tu_key" > my_agent/.env
echo "GOOGLE_GENAI_USE_VERTEXAI=FALSE" >> my_agent/.env

# 2. Indexar la base de conocimiento (una sola vez)
python ingest.py
# → "Listo. 10 chunks indexados en chroma_db/"

# 3. Levantar la UI web
adk web
# → http://127.0.0.1:8000
```

### 8.3 Cuándo re-indexar

Cada vez que cambien los `.md` de `rag/documents/`. La función `build_index()` borra la colección y la recrea limpia.

### 8.4 Verificación rápida

```bash
# Inspeccionar la DB de inscripciones
sqlite3 my_agent/inscripciones.db "SELECT * FROM inscripciones;"

# Listar colecciones de ChromaDB
python -c "import chromadb; c=chromadb.PersistentClient(path='my_agent/rag/chroma_db'); print([col.name for col in c.list_collections()])"
# → ['itba_knowledge']
```

---

## 9. Estructura de archivos

```
agente_austral_v1/
├── ingest.py                       # script offline para indexar el RAG
├── presentacion_ada_adk.html       # presentación didáctica (28 slides)
├── guia_adk.html                   # guía técnica de ADK con sección API key
├── spec.md                         # este documento
└── my_agent/
    ├── __init__.py                 # from . import agent
    ├── agent.py                    # define root_agent
    ├── prompt.py                   # SYSTEM_INSTRUCTION
    ├── tools.py                    # 5 tools
    ├── db.py                       # capa de acceso a SQLite
    ├── inscripciones.db            # SQLite (autogenerado)
    ├── .env                        # GOOGLE_API_KEY (NO commitear)
    ├── eval_set_1.evalset.json     # casos de evaluación ADK
    └── rag/
        ├── __init__.py
        ├── knowledge_base.py       # motor RAG (chunking, embed, search)
        ├── chroma_db/              # vector store local (sqlite-backed)
        └── documents/              # base de conocimiento (5 .md)
            ├── carreras_overview.md
            ├── ingenieria_informatica.md
            ├── ingenieria_industrial.md
            ├── ingenieria_electronica.md
            └── admision_y_aranceles.md
```

---

## 10. Flujos clave

### 10.1 Flujo de inscripción end-to-end

Input del usuario: *"Quiero anotarme en Videojuegos, mi legajo es 39071"*

```
1. ADK Web recibe el mensaje
2. Orquestador arma contexto: prompt + historial + mensaje + schemas
3. → Gemini: tool_call("search_knowledge_base", {query: "Videojuegos código informática"})
4. ← Tool retorna: {results: [{content: "...Videojuegos (INFO-410)..."}]}
5. → Gemini: tool_call("enroll_in_subject", {
       student_id: "39071",
       subject_code: "INFO-410",
       subject_name: "Videojuegos"
   })
6. tools.enroll_in_subject:
       a. db.is_enrolled("39071", "INFO-410") → False
       b. db.enroll(...) → INSERT exitoso
       c. retorna {success: True, inscripto_en: "14/05/2026 14:52", ...}
7. ← Gemini genera texto final: "¡Listo! Te inscribí en Videojuegos (INFO-410)..."
8. Respuesta vuelve al browser
```

### 10.2 Flujo de idempotencia

Si la misma inscripción se repite:

```
1. tools.enroll_in_subject(...)
2. db.is_enrolled(...) → True
3. retorna {success: False, already_enrolled: True, message: "Ya estás inscripto..."}
   → SIN INSERT a la DB
```

Si dos requests simultáneos pasan el chequeo Python al mismo tiempo (race condition):

```
Request A: db.is_enrolled() → False → INSERT exitoso
Request B: db.is_enrolled() → False → INSERT falla por UNIQUE constraint
         → SQLite tira IntegrityError → tool retorna error
         → el LLM responde amablemente "parece que hubo un problema, ya estás inscripto"
```

El constraint `UNIQUE` es la red de seguridad ante este caso.

---

## 11. Decisiones de diseño

### 11.1 ¿Por qué Google ADK y no LangChain/LlamaIndex/etc.?

- **Function calling nativo:** las tools son funciones Python normales, sin decorators ni configuración extra.
- **UI web incluida (`adk web`)**: facilita debugging y demos sin tener que construir frontend.
- **Eval sets:** sistema de evaluación con casos de prueba versionable como JSON.
- **Multi-lenguaje:** ADK también está disponible en Java, Go y TypeScript (no usado acá pero deja la puerta abierta).
- **Curva de aprendizaje baja:** un agente funcional en ~50 líneas.

### 11.2 ¿Por qué SQLite y no Postgres?

- **Zero setup:** ningún server, ningún proceso, solo un archivo.
- **Suficiente para este alcance:** miles de inscripciones, baja concurrencia.
- **Mismo motor que ChromaDB:** ya tenemos sqlite en las dependencias.
- **Migración trivial a Postgres** si crece: cambiar el conector, mismo esquema.

### 11.3 ¿Por qué RAG local con ChromaDB y no Vertex AI Search / Pinecone?

- **Costo cero**: corre 100% en local.
- **Velocidad de iteración:** modificar los docs y re-indexar tarda segundos.
- **Sin lock-in:** ChromaDB es open source y la API es estándar.
- **Tamaño manejable:** 10 chunks indexados no justifican un servicio externo.

### 11.4 ¿Por qué defensa en dos capas para idempotencia?

- La capa Python sola **no es suficiente:** dos requests simultáneos pueden pasar el chequeo `is_enrolled` al mismo tiempo.
- La capa SQL sola **es robusta pero da mala UX:** una excepción de `IntegrityError` no es un mensaje amigable.
- Juntas: el caso normal va por la rama amigable (`already_enrolled: True`); las races caen al fallback de SQL.

### 11.5 ¿Por qué similitud coseno y no euclidiana para el RAG?

Los embeddings semánticos capturan significado en la **dirección** del vector, no en su magnitud. Textos que dicen lo mismo con distinta longitud apuntan en la misma dirección pero tienen magnitudes distintas. El coseno ignora magnitud y compara solo dirección → métrica natural para significado.

---

## 12. Material didáctico generado

### 12.1 `presentacion_ada_adk.html`

Presentación de 29 slides, autocontenida (HTML + CSS + JS inline). Navegable con flechas, espacio, Home/End. Cubre:

- Qué es un agente (vs chatbot)
- Qué es Google ADK
- Arquitectura completa de Ada con diagrama
- El loop del orquestador paso a paso
- Anatomía de una tool y las 5 de Ada
- Pipeline RAG: indexación y búsqueda
- Similitud coseno con diagrama SVG y ejemplos
- Esquema SQLite y patrón de idempotencia
- Function calling con JSON real
- API key: dónde obtenerla y cómo cargarla
- Cómo correr el proyecto

### 12.2 `guia_adk.html`

Guía técnica de ADK con secciones de:
- ¿Qué es ADK? Conceptos clave
- Tools y ciclo de vida
- Arquitectura del agente
- Paso a paso de construcción
- **API key** (nueva sección agregada)
- RAG local
- Evals

---

## 13. Roadmap / trabajo futuro

### 13.1 Mejoras inmediatas

- [ ] Migrar de SQLite a Postgres si se necesita concurrencia real.
- [ ] Autenticación: validar que el `student_id` corresponde al usuario logueado.
- [ ] Lookup de materias por nombre fuzzy (actualmente depende del RAG, podría fallar con typos).
- [ ] Tool `unenroll_from_subject` para dar de baja inscripciones.
- [ ] Validación de correlatividades antes de inscribir.

### 13.2 Integraciones

- [ ] Conectar a la API real del SGA del ITBA (reemplaza `db.py` con cliente HTTP).
- [ ] Notificación por mail al confirmar inscripción.
- [ ] Sincronización de la base de conocimiento desde el sitio del ITBA (web scraping o API oficial).
- [ ] Integración con calendario académico para validar fechas de inscripción.

### 13.3 Evaluación y observabilidad

- [ ] Ampliar `eval_set_1.evalset.json` con más casos de prueba.
- [ ] Métricas de uso: % de inscripciones exitosas, tools más usadas, queries del RAG con baja relevancia.
- [ ] Logging estructurado para debugging.

### 13.4 Deploy

- [ ] Containerizar con Docker.
- [ ] Deploy en Cloud Run / similar.
- [ ] Secret Manager para la API key.
- [ ] HTTPS y rate limiting.

---

## 14. Glosario

| Término | Definición |
|---|---|
| **Agente** | Sistema que combina un LLM con tools para razonar y actuar. |
| **Tool** | Función Python que el LLM puede invocar vía function calling. |
| **Function calling** | Protocolo donde el LLM devuelve JSON estructurado pidiendo ejecutar una función. |
| **System prompt** | Instrucción inicial que define identidad, reglas y comportamiento del agente. |
| **RAG** | Retrieval-Augmented Generation: técnica que inyecta documentos relevantes al contexto del LLM antes de generar. |
| **Embedding** | Vector numérico que representa el significado semántico de un texto. |
| **Similitud coseno** | Métrica que mide el ángulo entre dos vectores (1 = idénticos, 0 = ortogonales, -1 = opuestos). |
| **Idempotencia** | Propiedad por la cual ejecutar una operación N veces produce el mismo resultado que ejecutarla una vez. |
| **Race condition** | Bug donde dos operaciones concurrentes producen un estado inconsistente. |
| **Orquestador** | Componente que coordina el ciclo LLM ↔ tools ↔ usuario. |
| **Chunking** | Dividir documentos largos en fragmentos más chicos para indexar en un vector store. |
