# Product Management API

A RESTful Product Management API built with FastAPI, PostgreSQL, SQLAlchemy, Redis, and Docker.


## Deployment Link : 

## Tech Stack

- Python 3.12
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Redis
- Pydantic
- Pytest
- Docker
- Nginx
- AWS EC2
- AWS CloudWatch

## Features

- User registration and authentication
- Role-based access control is enforced at the API boundary.
- Email passcode authentication
- JWT authentication
- Remember Me with sliding expiration
- Google OAuth
- Microsoft OAuth
- Github OAuth
- Product CRUD operations
- Product image upload
- Amazon S3 image storage
- Product search and filtering
- Pagination
- Product sorting
- Request ID logging
- CloudWatch application logging
- Unit tests with Pytest

---

# Requirements

Before running the application locally, install:

- Python 3.12+
- PostgreSQL
- Redis
- Docker
- Docker Compose

---

# Local Development

## 1. Clone the repository

```bash
git clone git@github.com:interloid/product-management-api.git
cd product-management-api
```

## 2. Create virtual environment

```bash
python3 -m venv .venv
```

Activate it:

### Linux / macOS

```bash
source .venv/bin/activate
```

### Windows

```powershell
.venv\Scripts\activate
```

## 3. Install dependencies

```bash
uv sync
```

---

# Database Migration

Run all Alembic migrations:

```bash
alembic upgrade head
```

To create a new migration:

```bash
alembic revision --autogenerate -m "your migration message"
```

Then apply it:

```bash
alembic upgrade head
```

---

# Run the Application

Start FastAPI with Uvicorn:

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://localhost:8000
```

Swagger documentation:

```text
http://localhost:8000/docs
```

ReDoc:

```text
http://localhost:8000/redoc
```

---

# Running with Docker

Build the Docker image:

```bash
docker build -t product-management-api .
```

Run with Docker Compose:

```bash
docker compose up -d
```

Check running containers:

```bash
docker compose ps
```

View application logs:

```bash
docker compose logs -f api
```

Stop the application:

```bash
docker compose down
```

---

# Database Migration with Docker

Run Alembic inside the API container:

```bash
docker compose exec api alembic upgrade head
```

---

# Testing

Run all tests:

```bash
pytest
```

Run unit tests:

```bash
pytest tests/unit
```

Run with coverage:

```bash
pytest --cov=app
```

---

# API Authentication

The application uses JWT access tokens and opaque refresh tokens.

After successful login, the backend:
- Returns a short-lived JWT access token.
- Sets the opaque refresh token as a secure, HTTP-only cookie.
- Stores only the refresh token’s hash in PostgreSQL.

The frontend must send credentials with requests:

```javascript
fetch(url, {
  headers: {
    Authorization: `Bearer ${accessToken}`,
  },
  credentials: "include",
});
```

## Remember Me

Normal login:

```text
REFRESH_TOKEN_EXPIRE_DAYS=7
```

Remember Me:

```text
REMEMBER_ME_EXPIRE_DAYS=30
```

When `remember_me=true`, the refresh token and cookie use the longer expiration period. The access token remains short-lived in both cases.

---

# Product API

Main endpoints:

```text
POST   /api/v1/products
GET    /api/v1/products
GET    /api/v1/products/{id}
PATCH  /api/v1/products/{id}
DELETE /api/v1/products/{id}
```

Product creation uses:

```text
multipart/form-data
```

because product data and product images are uploaded together.

Product update uses the API's update request format.

---

# Product Images

Product images are uploaded to Amazon S3.

The database stores the image metadata/object key while the actual image file is stored in S3.

---

# Logging

The application generates request-based logs containing:

```text
timestamp
log level
request ID
HTTP method
request path
logger name
message
```

Example:

```text
2026-08-24 08:55:09 | INFO | request_id=... | GET | /api/v1/products | ... | Request started
```

In production, Docker sends container logs to AWS CloudWatch.

---

# Production Deployment

Production architecture:

```text
Frontend
   |
   v
Nginx
   |
   v
Docker Container
   |
   v
FastAPI
   |
   +---- PostgreSQL
   |
   +---- Redis
   |
   +---- Amazon S3
   |
   +---- SMTP
   |
   +---- CloudWatch Logs
```

Production server:

```text
AWS EC2
```

Docker Compose runs the API container.

CloudWatch receives application logs through the Docker `awslogs` logging driver.

---

# Production Docker Commands

Pull the latest image:

```bash
docker compose pull
```

Start/recreate the application:

```bash
docker compose up -d --force-recreate
```

Check status:

```bash
docker compose ps
```

Check container logs:

```bash
docker logs product-management-api
```

Check the logging driver:

```bash
docker inspect product-management-api \
  --format '{{.HostConfig.LogConfig.Type}}'
```

Expected:

```text
awslogs
```

---

# AWS CloudWatch

Production logs are available in:

```text
CloudWatch
└── Logs
    └── /product-management-api
```

The application uses AWS CloudWatch for centralized production logging.

Developers/authorized users can inspect:

* Request ID
* HTTP method
* Endpoint
* Status code
* Request duration
* Application errors


---

# Project Structure

```text
app/
├── api/
├── core/
├── db/
├── exceptions/
├── middleware/
├── models/
├── repositories/
├── schemas/
├── services/
├── templates/
└── utils/

tests/
├── unit/
└── ...

alembic/
├── versions/
└── ...

scripts/

Dockerfile
docker-compose.yml
pyproject.toml
alembic.ini
README.md
```

---

# Development Workflow

Typical development workflow:

```bash
git pull

# Install/update dependencies
uv sync

# Apply migrations
alembic upgrade head

# Run application
uvicorn app.main:app --reload

# Run tests
pytest
```

For Docker:

```bash
docker compose up -d
docker compose ps
docker compose logs -f api
```

