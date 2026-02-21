Deploy the latest code to DigitalOcean VPS.

Pre-flight checklist:
1. Confirm all changes are committed: `git status`
2. Push to GitHub: `git push origin main`

Then provide the SSH deployment commands for the user to run on their VPS:
```bash
ssh root@YOUR_VPS_IP
cd taskmanagerboss
git pull origin main
docker-compose down
docker-compose up --build -d
docker-compose logs -f bot
```

Remind them to NEVER copy the .env file via git — it must be manually placed on the server.
