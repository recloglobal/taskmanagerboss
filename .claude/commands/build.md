Rebuild and restart the Docker containers for this project.

Run: `docker-compose down && docker-compose up --build`

Watch the logs and confirm:
1. `db-1 | database system is ready to accept connections`
2. `bot-1 | Bot is running...`
3. `bot-1 | Application started`

If there are errors, diagnose and fix them.
