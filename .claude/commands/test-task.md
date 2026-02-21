Test the full task flow end to end.

Steps:
1. Check that all containers are running: `docker-compose ps`
2. Check the tasks table current state: `docker-compose exec db psql -U taskbot -d taskbot_db -c "SELECT id, text, category, status FROM tasks ORDER BY created_at DESC LIMIT 5;"`
3. Remind me to send a test message to #general in the Telegram group
4. After I confirm I sent it, check if the task appeared in the database
5. Report the result
