---
name: openrouter
description: OpenRouter AI provider patterns for this project. Use when modifying AI model selection, adding new models, adjusting fallback logic, or debugging OpenRouter API calls.
---

# OpenRouter Skill

## What It Is
OpenRouter is a unified API gateway to 300+ LLMs using an OpenAI-compatible interface.
This project uses it in `app/ai.py` via the `openai` Python SDK.

## Model Setup
```python
PRIMARY_MODEL  = "meta-llama/llama-3.3-70b-instruct"   # Free-tier friendly, fast
FALLBACK_MODEL = "google/gemini-2.0-flash-001"          # Fallback if primary fails
```

## Client Initialization
```python
from openai import OpenAI
from config import OPENROUTER_API_KEY

_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)
```

## Calling the API
```python
response = _client.chat.completions.create(
    model="meta-llama/llama-3.3-70b-instruct",
    messages=[{"role": "user", "content": "your prompt"}],
)
text = response.choices[0].message.content.strip()
```

## Fallback Pattern (used in this project)
```python
for model in (PRIMARY_MODEL, FALLBACK_MODEL):
    try:
        response = _client.chat.completions.create(model=model, messages=messages)
        return response.choices[0].message.content.strip()
    except Exception:
        if model == FALLBACK_MODEL:
            raise  # Both failed — let it bubble up
```

## Environment Variable
- `OPENROUTER_API_KEY` — set in `.env`, loaded via `config.py`
- Get your key at: https://openrouter.ai/keys

## Finding Model IDs
Browse at https://openrouter.ai/models — copy the model ID exactly (e.g. `meta-llama/llama-3.3-70b-instruct`).

## Key Differences from Gemini SDK
| Gemini (`google-generativeai`) | OpenRouter (`openai` SDK) |
|---|---|
| `model.generate_content(prompt)` | `client.chat.completions.create(model=..., messages=[...])` |
| `response.text` | `response.choices[0].message.content` |
| Single string prompt | List of `{role, content}` dicts |
| Separate history API | Standard `messages` list for multi-turn |

## Common Issues
- `401 Unauthorized` — check `OPENROUTER_API_KEY` in `.env`
- `404 Not Found` — wrong model ID; verify at openrouter.ai/models
- Rate limits — OpenRouter has generous free limits; primary failure triggers fallback automatically
