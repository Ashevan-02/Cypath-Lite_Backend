### CyPath Lite (FastAPI Backend)

Production-ready backend for **CyPath Lite** — an AI-assisted bicycle lane violation detection system.

#### Features
- JWT authentication (OAuth2) for all endpoints except `/auth/register` and `/auth/login`
- Role-based authorization: **ADMIN** and **ANALYST**
- Video upload with validation + metadata persistence
- ROI (Region of Interest) management per video
- Background analysis via Celery (YOLO-based detections + violation logic + persistence)
- Violation listing + analytics summary
- Report generation (PDF + CSV) and download
- Evidence frames saved with overlays (ROI polygon + detections)

---

### Prerequisites
- Python **3.10+**
- PostgreSQL
- Redis
- (For full ML functionality) YOLO model file at `MODEL_PATH`

---

### Setup

#### 1) Create a virtual environment
```bash
python -m venv venv
```

#### 2) Install dependencies
```bash
pip install -r requirements/base.txt
pip install -r requirements/dev.txt
```

#### 3) Configure environment variables
1. Copy `.env.example` to `.env`
2. Update secrets/passwords.

---

### Database

This project includes `scripts/init_db.py` to create tables and bootstrap default users.

#### Run initialization
```bash
python scripts/init_db.py
```

> Note: `migrations/` is intentionally empty for now; `init_db.py` is equivalent to an initial migration step.

---

### Start services (Docker)

```bash
docker compose up --build
```

To run only Postgres + Redis:
```bash
docker compose up postgres redis
```

---

### Start the Celery worker

In a new terminal:
```bash
celery -A app.core.celery_app.celery_app worker --loglevel=info
```

---

### Start the FastAPI application

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

### API Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

JWT Authorization button is available in Swagger UI.

---

### Testing

```bash
pytest -q
```

