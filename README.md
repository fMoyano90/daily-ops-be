# DailyOps

Sistema de gestión de operaciones diarias multi-usuario. Planifica, ejecuta y mide tu trabajo diario.

## Arquitectura

- **Backend**: FastAPI (async) + SQLAlchemy + PostgreSQL + APScheduler
- **Frontend**: Next.js 16 + React 19 + Tailwind CSS + Zustand
- **Auth**: JWT (access + refresh tokens), bcrypt password hashing

## Setup del Backend

### Requisitos

- Python 3.12+
- PostgreSQL 14+

### Instalación

```bash
cd fastapi-project

# 1. Crear entorno virtual
python -m venv .venv && source .venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores (ver tabla abajo)

# 4. Ejecutar migraciones (crea tablas + usuario founder)
.venv/bin/alembic upgrade head

# 5. Seed de proyectos iniciales (opcional)
.venv/bin/python -m app.seed

# 6. Iniciar servidor
.venv/bin/uvicorn app.main:app --reload
```

### Variables de entorno del Backend

| Variable | Requerida | Descripción | Ejemplo |
|---|---|---|---|
| `DATABASE_URL` | Sí | URL de conexión a PostgreSQL | `postgresql+asyncpg://user:pass@localhost:5432/dailyops` |
| `CORS_ORIGINS` | No | Orígenes CORS permitidos | `["http://localhost:3000"]` |
| `APP_NAME` | No | Nombre de la aplicación | `DailyOps API` |
| `APP_VERSION` | No | Versión | `0.2.0` |
| `JIRA_ENCRYPTION_KEY` | No | Clave Fernet para cifrar tokens Jira | `tu-clave-fernet-de-32-bytes` |
| `JIRA_SYNC_ENABLED` | No | Habilitar scheduler de sync Jira | `true` |
| `JIRA_SYNC_INTERVAL_MINUTES` | No | Intervalo de sync Jira (min) | `30` |
| `AUTO_CLOSE_ENABLED` | No | Habilitar cierre automático de días | `true` |
| `AUTO_CLOSE_HOUR` | No | Hora del cierre automático | `0` |
| `AUTO_CLOSE_MINUTE` | No | Minuto del cierre automático | `1` |
| `JWT_SECRET_KEY` | Sí | Clave secreta para firmar JWTs | `secrets.token_urlsafe(32)` |
| `JWT_ALGORITHM` | No | Algoritmo JWT | `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | Expiración access token (min) | `60` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | No | Expiración refresh token (días) | `30` |
| `FOUNDER_EMAIL` | No | Email del usuario fundador | `f.moyano90@gmail.com` |
| `FOUNDER_PASSWORD` | No | Contraseña del usuario fundador | `tu-contraseña-segura` |
| `FOUNDER_DISPLAY_NAME` | No | Nombre visible del fundador | `Felipe Moyano` |

### Generar JWT_SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Migraciones

```bash
# Aplicar todas las migraciones pendientes
.venv/bin/alembic upgrade head

# Crear nueva migración
.venv/bin/alembic revision --autogenerate -m "descripcion"

# Revertir última migración
.venv/bin/alembic downgrade -1
```

### API Endpoints

#### Auth
- `POST /api/v1/auth/login` — Iniciar sesión (email + password → tokens JWT)
- `POST /api/v1/auth/refresh?token=<refresh>` — Renovar access token
- `GET /api/v1/auth/me` — Datos del usuario logueado

#### Proyectos
- `GET /api/v1/projects` — Listar
- `POST /api/v1/projects` — Crear
- `PATCH /api/v1/projects/{id}` — Actualizar
- `DELETE /api/v1/projects/{id}` — Eliminar

#### Tareas
- `GET /api/v1/tasks` — Listar (filtros: project, status, source, category, priority)
- `GET /api/v1/tasks/backlog` — Backlog + recurrentes omitidas
- `POST /api/v1/tasks` — Crear
- `GET /api/v1/tasks/{id}` — Obtener
- `PATCH /api/v1/tasks/{id}` — Actualizar
- `DELETE /api/v1/tasks/{id}` — Eliminar

#### Plan diario
- `GET /api/v1/daily-plans/today` — Plan de hoy (auto-crea si no existe)
- `GET /api/v1/daily-plans/{date}` — Plan por fecha
- `POST /api/v1/daily-plans` — Crear plan
- `POST /api/v1/daily-plans/today/tasks` — Seleccionar tareas para hoy
- `POST /api/v1/daily-plans/{id}/tasks` — Agregar tarea al plan
- `GET /api/v1/daily-plans/today/suggestions` — Sugerencias para hoy
- `POST /api/v1/daily-plans/{id}/close` — Cerrar día
- `POST /api/v1/daily-plans/{id}/reopen` — Reabrir día
- `PUT /api/v1/daily-plans/{id}/tasks/order` — Reordenar tareas

#### Tareas del plan
- `PATCH /api/v1/daily-tasks/{id}` — Actualizar
- `POST /api/v1/daily-tasks/{id}/complete` — Completar
- `DELETE /api/v1/daily-tasks/{id}` — Eliminar

#### Subtareas
- `GET /api/v1/daily-tasks/{task_id}/subtasks` — Listar
- `POST /api/v1/daily-tasks/{task_id}/subtasks` — Crear
- `PATCH /api/v1/daily-tasks/{task_id}/subtasks/{id}` — Actualizar
- `DELETE /api/v1/daily-tasks/{task_id}/subtasks/{id}` — Eliminar

#### Timer
- `POST /api/v1/daily-tasks/{task_id}/timer/start` — Iniciar
- `POST /api/v1/daily-tasks/{task_id}/timer/pause` — Pausar
- `POST /api/v1/daily-tasks/{task_id}/timer/resume` — Reanudar
- `POST /api/v1/daily-tasks/{task_id}/timer/stop` — Detener
- `POST /api/v1/daily-tasks/{task_id}/timer/reset` — Reiniciar
- `GET /api/v1/daily-tasks/{task_id}/timer/sessions` — Historial de sesiones

#### Tareas recurrentes
- `GET /api/v1/recurring-tasks` — Listar (con estadísticas)
- `POST /api/v1/recurring-tasks` — Crear
- `PATCH /api/v1/recurring-tasks/{id}` — Actualizar
- `DELETE /api/v1/recurring-tasks/{id}` — Eliminar
- `GET /api/v1/recurring-tasks/{id}/history` — Historial de instancias

#### Conexiones Jira
- `GET /api/v1/jira-connections` — Listar
- `POST /api/v1/jira-connections` — Crear
- `PATCH /api/v1/jira-connections/{id}` — Actualizar
- `DELETE /api/v1/jira-connections/{id}` — Eliminar
- `POST /api/v1/jira-connections/{id}/test` — Probar conexión
- `POST /api/v1/jira-connections/{id}/sync` — Sincronizar
- `POST /api/v1/jira-connections/sync-all` — Sincronizar todas

#### Comentarios
- `GET /api/v1/tasks/{task_id}/comments` — Listar
- `POST /api/v1/tasks/{task_id}/comments` — Crear
- `PATCH /api/v1/task-comments/{id}` — Actualizar
- `DELETE /api/v1/task-comments/{id}` — Eliminar

#### Historial
- `GET /api/v1/history` — Planes cerrados (filtros por fecha)
- `GET /api/v1/history/{date}` — Plan por fecha
- `GET /api/v1/history/summary/week` — Resumen semanal

#### Health
- `GET /` — Root
- `GET /health` — Health check

---

## Setup del Frontend

### Requisitos

- Node.js 20+
- Backend corriendo en `http://localhost:8000`

### Instalación

```bash
cd my-app

# 1. Instalar dependencias
npm install

# 2. Configurar variables de entorno (opcional)
cp .env.local.example .env.local

# 3. Iniciar servidor de desarrollo
npm run dev
```

### Variables de entorno del Frontend

| Variable | Requerida | Descripción | Ejemplo |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | No | URL base de la API | `http://localhost:8000/api/v1` |

### Producción

```bash
npm run build
npm start
```

---

## Autenticación

### Flujo

1. El usuario ingresa email + contraseña en `/login`
2. El backend valida y retorna `access_token` + `refresh_token` (JWT)
3. El frontend guarda los tokens en `localStorage`
4. Cada request incluye `Authorization: Bearer <access_token>`
5. Si el access token expira (401), se intenta renovar con el refresh token
6. Si el refresh también falla, se hace logout y redirect a `/login`

### Usuario fundador

Se crea automáticamente al correr la migración `alembic upgrade head`:
- **Email**: `f.moyano90@gmail.com` (configurable via `FOUNDER_EMAIL`)
- **Contraseña**: `47163978Fmc..` (configurable via `FOUNDER_PASSWORD`)
- **Nombre**: `Felipe Moyano` (configurable via `FOUNDER_DISPLAY_NAME`)

Todos los datos existentes se asocian automáticamente al usuario fundador durante la migración.

### Multi-usuario (futuro)

La arquitectura ya soporta múltiples usuarios:
- Cada usuario tiene sus propios datos aislados (proyectos, tareas, planes, etc.)
- Para habilitar registro público, agregar endpoint `POST /api/v1/auth/register`
- Para invitaciones, agregar sistema de invites con token único

---

## Estructura de archivos

### Backend

```
fastapi-project/
├── app/
│   ├── main.py              # Entrypoint, routers, CORS
│   ├── config.py            # Settings via pydantic-settings
│   ├── database.py          # Engine y session async
│   ├── dependencies.py      # Auth: get_current_user, JWT utils
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py          # Usuarios
│   │   ├── project.py       # Proyectos
│   │   ├── task.py          # Tareas
│   │   ├── daily_plan.py    # Plan diario
│   │   ├── daily_task.py    # Tarea del plan
│   │   ├── daily_subtask.py # Subtarea
│   │   ├── timer_session.py # Sesiones de timer
│   │   ├── recurring_task.py# Tareas recurrentes
│   │   ├── jira_connection.py# Conexiones Jira
│   │   └── task_comment.py  # Comentarios
│   ├── schemas/             # Pydantic schemas
│   │   └── auth.py          # Auth schemas
│   ├── routers/             # API endpoints
│   │   ├── auth.py          # Login, refresh, me
│   │   ├── projects.py
│   │   ├── tasks.py
│   │   ├── daily_plans.py
│   │   ├── daily_tasks.py
│   │   ├── subtasks.py
│   │   ├── timers.py
│   │   ├── history.py
│   │   ├── recurring_tasks.py
│   │   ├── jira_connections.py
│   │   └── task_comments.py
│   └── services/            # Lógica de negocio
│       ├── scheduler.py     # APScheduler
│       ├── jira_sync.py     # Sync Jira
│       ├── jira_client.py   # Cliente Jira API
│       ├── crypto.py        # Cifrado Fernet
│       ├── recurring_engine.py
│       └── day_closer.py    # Cierre de día
├── alembic/                 # Migraciones de BD
├── requirements.txt
└── .env.example
```

### Frontend

```
my-app/
├── src/
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── layout.tsx   # Layout sin sidebar
│   │   │   └── login/
│   │   │       └── page.tsx # Página de login
│   │   ├── (main)/
│   │   │   ├── layout.tsx   # Auth guard + MainLayout
│   │   │   ├── today/
│   │   │   ├── backlog/
│   │   │   ├── history/
│   │   │   ├── settings/
│   │   │   ├── recurring/
│   │   │   └── add-task/
│   │   ├── layout.tsx       # Root layout
│   │   ├── page.tsx         # Redirect condicional
│   │   └── globals.css
│   ├── components/
│   │   └── layout/
│   │       ├── Header.tsx   # Con user menu + logout
│   │       ├── Sidebar.tsx
│   │       └── MainLayout.tsx
│   ├── lib/
│   │   ├── api.ts           # API client + JWT interceptor
│   │   ├── types.ts         # TypeScript types
│   │   ├── utils.ts
│   │   └── theme.ts
│   └── stores/
│       ├── authStore.ts     # Auth state (Zustand)
│       └── dailyStore.ts    # Timer state (Zustand)
├── package.json
└── .env.local
```
