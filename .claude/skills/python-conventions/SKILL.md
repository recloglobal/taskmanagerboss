---
name: python-conventions
description: Python coding patterns for this project. Use when writing any Python code, async functions, SQLAlchemy queries, or database operations.
---

# Python Conventions for TaskManagerBoss

## Async Rules
- ALL database calls must use `async with SessionLocal() as session:`
- ALL handlers must be `async def`
- Use `await` for every database operation
- Never use sync SQLAlchemy in async context

## SQLAlchemy Pattern
```python
# Correct pattern for queries
async with SessionLocal() as session:
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task:
        task.status = "done"
        await session.commit()
```

## Error Handling
- Always wrap Telegram API calls in try/except
- Log errors with: `logger.error(f"Description: {e}")`
- Never let exceptions crash the bot silently

## Imports Order
1. Standard library
2. Third party (telegram, sqlalchemy, google)
3. Local (config, database, models, ai)

## Environment Variables
- Always load from `config.py` — never use `os.getenv()` directly in handlers
