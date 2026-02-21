---
name: docker-workflow
description: Docker commands and workflows for this project. Use when working with containers, running migrations, checking logs, or debugging container issues.
---

# Docker Workflow

## Basic Commands
```bash
docker-compose up --build          # Full rebuild and start
docker-compose up -d               # Start in background
docker-compose down                # Stop everything
docker-compose restart bot         # Restart bot only (fastest for code changes)
docker-compose logs -f bot         # Follow bot logs
docker-compose logs -f db          # Follow postgres logs
```

## Run Migrations (ALWAYS inside container)
```bash
docker-compose exec bot bash
alembic revision --autogenerate -m "your description"
alembic upgrade head
exit
```

## Database Inspection
```bash
docker-compose exec db psql -U taskbot -d taskbot_db
\dt                                # List all tables
SELECT * FROM tasks;               # View all tasks
\q                                 # Quit
```

## After Code Changes
```bash
docker-compose restart bot         # If only Python files changed
docker-compose up --build          # If requirements.txt changed
```

## Common Issues
- "Connection refused" to postgres: wait for healthcheck, postgres takes ~5s to start
- "Module not found": rebuild with `docker-compose up --build`
- "Port already in use": `docker-compose down` first
