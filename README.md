# DevOps Lab

A Python/FastAPI application built as a learning project for DevOps fundamentals.

## What This Project Covers

- FastAPI REST API with health and version endpoints
- Automated testing with pytest
- CI pipeline with GitHub Actions (runs on every push and PR)
- Containerization with Docker and docker-compose
- CD pipeline via Coolify (deploys automatically when tests pass)
- PostgreSQL database with automated S3 backups
- CloudWatch monitoring on AWS EC2

## Running Locally

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Docker Desktop

### Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/devops-lab.git
cd devops-lab

# Copy environment config and fill in your values
cp .env.example .env

# Install dependencies
uv sync

# Run the app
uv run uvicorn main:app --reload
```

Open http://localhost:8000/docs to see the interactive API documentation.

### Running Tests

```bash
APP_ENV=test uv run pytest -v
```

### Running with Docker

```bash
docker compose up --build
```

## Environment Variables

See `.env.example` for all required variables and descriptions.

## CI/CD Pipeline

- **CI:** GitHub Actions runs `pytest` on every push and pull request
- **CD:** On merge to `main`, if tests pass, Coolify automatically deploys to the server

## Project Structure

```
devops-lab/
├── main.py              # FastAPI application
├── test_main.py         # Tests
├── Dockerfile           # Container image definition
├── docker-compose.yml   # Multi-container setup
├── pyproject.toml       # Python dependencies
├── .env.example         # Environment variable template
└── .github/
    └── workflows/
        └── ci.yml       # GitHub Actions CI/CD pipeline
```