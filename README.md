# llm-triage-api

A small API that takes a customer message and returns a triage result: a category, an urgency, a confidence score, and a short reason. (Work in progress for the FlyRank Internship, Week 7.)

## Setup

1. Copy `.env.example` to `.env` and fill in your own values:
   - `LLM_BASE_URL`
   - `LLM_API_KEY`
   - `LLM_MODEL`
2. Install the dependencies and start the server:

```bash
python -m pip install fastapi uvicorn python-dotenv openai
source venv/Scripts/activate
export LLM_STUB=1
uvicorn main:app --reload
```

`LLM_STUB=1` is stub mode. The server skips the model and returns a fixed, hardcoded answer, so the endpoint, validation, and curl commands can be tested without spending model calls. Without it, `/triage` returns `501 Not Implemented` until the model is wired in (Stage 2).

## Endpoint

`POST /triage`

Input:

```json
{"text": "string, 1 to 2000 characters"}
```

Output:

```json
{
  "category": "billing | bug | feature | account | other",
  "urgency": "low | normal | high",
  "confidence": "number from 0 to 1",
  "reason": "string, 1 to 2000 characters"
}
```

## Example 1: valid request

```bash
curl -i -X POST http://127.0.0.1:8000/triage -H "Content-Type: application/json" -d '{"text": "I was charged twice"}'
```

Response (200):

```json
{"category":"billing","urgency":"low","confidence":0.83,"reason":"stub answer"}
```

## Example 2: invalid request

The field name is wrong (`txt` instead of `text`):

```bash
curl -i -X POST http://127.0.0.1:8000/triage -H "Content-Type: application/json" -d '{"txt": "I was charged twice"}'
```

Response (400):

```json
{"detail":[{"type":"missing","loc":["body","text"],"msg":"Field required","input":{"txt":"I was charged twice"}}]}
```

## Input validation

FastAPI normally returns 422 for invalid input. This project overrides that handler so every validation failure returns **400** and names the offending field in `loc`.

| Bad input | `type` in the response |
|---|---|
| Wrong or missing field name | `missing` |
| Empty text | `string_too_short` |
| Text over 2000 characters | `string_too_long` |

## Status

- [x] Stage 0: setup and smoke test
- [x] Stage 1: endpoint, input validation, output schema, stub mode
- [ ] Stage 2: prompt as a versioned file
- [ ] Stage 3: parse, validate, repair, quarantine
- [ ] Stage 4: timeout, retries, cost logging, kill switch
- [ ] Stage 5: evals and final README

## Stage 2 observations

- Clean billing message: correct, valid JSON. First run had leading newlines; a later run was clean (`cohere/north-mini-code:free`).
- Ambiguous message: returned `other` with low confidence, but the reason matched my own prompt example, so this is weak evidence.
- Hijack attempt: first run returned non-JSON safety-style text (model not logged). Second run, served by `liquid/lfm-2.5-2.6b:free`, returned clean JSON and classified it as `other`. It used confidence 0.4 although my prompt said 0.3 or below.
- The free router picks a different model per call (OpenRouter's dashboard showed 4+ models across 6 requests), so output format varies. This is why Stage 3 validates every response.