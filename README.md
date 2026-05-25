# DailyOps API

Backend de gestión de operaciones diarias construido con **FastAPI** (async), **SQLAlchemy**, **PostgreSQL** y **APScheduler**.

## Requisitos

- Python 3.11+
- PostgreSQL 14+

## Setup

```bash
cp .env.example .env
# editar DATABASE_URL y otras variables

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# migraciones
alembic upgrade head

# seed de proyectos
python -m app.seed

# iniciar servidor
uvicorn app.main:app --reload
```

## Variables de entorno

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | URL de conexión a PostgreSQL (ej: `postgresql+asyncpg://user:pass@localhost/db`) |
| `CORS_ORIGINS` | Orígenes CORS permitidos (por defecto `["http://localhost:3000"]`) |
| `APP_NAME` | Nombre de la aplicación |
| `APP_VERSION` | Versión |
| `JIRA_ENCRYPTION_KEY` | Clave Fernet para cifrar tokens Jira |
| `JIRA_SYNC_ENABLED` | Habilitar scheduler de sincronización Jira |
| `JIRA_SYNC_INTERVAL_MINUTES` | Intervalo de sincronización (default: 30 min) |

## Arquitectura

```
app/
├── main.py              # Entrypoint, routers, CORS
├── config.py            # Settings via pydantic-settings
├── database.py          # Engine y session async
├── models/              # SQLAlchemy models
│   ├── project.py       # Proyectos (work, business, partner, personal)
│   ├── task.py          # Tareas generales
│   ├── daily_plan.py    # Plan diario
│   ├── daily_task.py    # Tarea dentro de un plan diario
│   ├── daily_subtask.py # Subtarea
│   ├── timer_session.py # Sesiones de temporizador
│   ├── recurring_task.py# Tareas recurrentes + instancias
│   ├── jira_connection.py# Conexiones Jira
│   └── task_comment.py  # Comentarios en tareas
├── schemas/             # Pydantic schemas (request/response)
├── routers/             # API endpoints
│   ├── projects.py      # CRUD proyectos
│   ├── tasks.py         # CRUD tareas + backlog
│   ├── daily_plans.py   # Plan diario + close day
│   ├── daily_tasks.py   # CRUD tareas del plan
│   ├── subtasks.py      # CRUD subtareas
│   ├── timers.py        # Start/pause/resume/stop timer
│   ├── history.py       # Historial de planes cerrados
│   ├── recurring_tasks.py # CRUD recurrentes + auto-add
│   ├── jira_connections.py # CRUD conexiones + sync
│   └── task_comments.py # Comentarios en tareas
├── services/            # Lógica de negocio
│   ├── crypto.py        # Cifrado Fernet para tokens Jira
│   ├── jira_client.py   # Cliente HTTP para API Jira
│   ├── jira_sync.py     # Sincronización Jira → tareas locales
│   ├── recurring_engine.py # Motor de tareas recurrentes
│   ├── scheduler.py     # APScheduler para Jira sync
│   └── day_closer.py    # Cierre de plan diario
└── seed.py              # Seed de proyectos iniciales
```

## API endpoints

### Proyectos
- `GET /api/v1/projects` — listar
- `POST /api/v1/projects` — crear
- `PATCH /api/v1/projects/{id}` — actualizar

### Tareas
- `GET /api/v1/tasks` — listar (filtros: project, status, source, category, priority)
- `GET /api/v1/tasks/backlog` — backlog + recurrentes omitidas
- `POST /api/v1/tasks` — crear
- `GET /api/v1/tasks/{id}` — obtener
- `PATCH /api/v1/tasks/{id}` — actualizar
- `DELETE /api/v1/tasks/{id}` — eliminar

### Plan diario
- `GET /api/v1/daily-plans/today` — plan de hoy (auto-crea si no existe)
- `POST /api/v1/daily-plans/{id}/close` — cerrar día (completa/rolled-over tareas)
- `GET /api/v1/daily-plans/{id}` — obtener plan
- `PATCH /api/v1/daily-plans/{id}` — actualizar notas/status

### Tareas del plan
- `GET /api/v1/daily-plans/{plan_id}/tasks` — listar tareas del plan
- `POST /api/v1/daily-plans/{plan_id}/tasks` — agregar tarea
- `PATCH /api/v1/daily-plans/{plan_id}/tasks/{id}` — actualizar status/orden
- `DELETE /api/v1/daily-plans/{plan_id}/tasks/{id}` — remover
- `PUT /api/v1/daily-plans/{plan_id}/tasks/reorder` — reordenar

### Subtareas
- `GET /api/v1/daily-plans/{plan_id}/tasks/{task_id}/subtasks` — listar
- `POST /api/v1/daily-plans/{plan_id}/tasks/{task_id}/subtasks` — crear
- `PATCH /api/v1/daily-plans/{plan_id}/tasks/{task_id}/subtasks/{id}` — actualizar
- `DELETE /api/v1/daily-plans/{plan_id}/tasks/{task_id}/subtasks/{id}` — eliminar

### Timer
- `POST /api/v1/daily-tasks/{task_id}/timer/start` — iniciar
- `POST /api/v1/daily-tasks/{task_id}/timer/pause` — pausar
- `POST /api/v1/daily-tasks/{task_id}/timer/resume` — reanudar
- `POST /api/v1/daily-tasks/{task_id}/timer/stop` — detener
- `POST /api/v1/daily-tasks/{task_id}/timer/reset` — reiniciar
- `GET /api/v1/daily-tasks/{task_id}/timer/sessions` — historial de sesiones

### Tareas recurrentes
- `GET /api/v1/recurring-tasks` — listar (con estadísticas)
- `POST /api/v1/recurring-tasks` — crear
- `PATCH /api/v1/recurring-tasks/{id}` — actualizar
- `DELETE /api/v1/recurring-tasks/{id}` — eliminar
- `POST /api/v1/recurring-tasks/{id}/skip` — omitir instancia
- `GET /api/v1/recurring-tasks/{id}/history` — historial de instancias
- `POST /api/v1/recurring-tasks/auto-add` — agregar recurrentes al plan de hoy

### Conexiones Jira
- `GET /api/v1/jira-connections` — listar
- `POST /api/v1/jira-connections` — crear (token se cifra)
- `PATCH /api/v1/jira-connections/{id}` — actualizar
- `DELETE /api/v1/jira-connections/{id}` — eliminar
- `POST /api/v1/jira-connections/{id}/test` — probar conexión
- `POST /api/v1/jira-connections/{id}/sync` — sincronizar
- `POST /api/v1/jira-connections/sync-all` — sincronizar todas

### Comentarios
- `GET /api/v1/tasks/{task_id}/comments` — listar
- `POST /api/v1/tasks/{task_id}/comments` — crear
- `PATCH /api/v1/tasks/{task_id}/comments/{id}` — actualizar
- `DELETE /api/v1/tasks/{task_id}/comments/{id}` — eliminar

### Historial
- `GET /api/v1/history` — planes cerrados (paginado, filtros por fecha)

### Health
- `GET /` — root
- `GET /health` — health check

## Migraciones

```bash
# crear nueva migración
alembic revision --autogenerate -m "descripcion"

# aplicar
alembic upgrade head

# revertir
alembic downgrade -1
```

## Seed

```bash
python -m app.seed
```

Crea 8 proyectos por defecto: SMU, Núcleo Gestor, SubTech, SubVitals, Wingenroth, Familia, Salud, Pareja.
