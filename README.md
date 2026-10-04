# llm-triage-api

A small web API that reads one customer support message and sorts it for you. You send it text like "I was charged twice", and it replies with a category (billing, bug, feature, account, or other), an urgency (low, normal, or high), a confidence score from 0 to 1, and a one-sentence reason. An AI model makes the decision, but the code checks every answer before returning it, so callers only ever get data in the exact shape promised.

## Try it

Start the server (the model must be reachable and `.env` filled in):

```bash
uvicorn main:app --reload
```

Send a request:

```bash
curl -i -X POST http://127.0.0.1:8000/triage -H "Content-Type: application/json" -d '{"text": "My password reset email never arrives"}'
```

Response (200):

```json
{"category":"account","urgency":"normal","confidence":0.9,"reason":"The customer reports not receiving a password reset email, which is an account-related issue."}
```

Invalid input returns **400** and names the field:

```bash
curl -i -X POST http://127.0.0.1:8000/triage -H "Content-Type: application/json" -d '{"txt": "I was charged twice"}'
```

```json
{"detail":[{"type":"missing","loc":["body","text"],"msg":"Field required","input":{"txt":"I was charged twice"}}]}
```

## Job card

```
What it does (one sentence): Classifies an incoming support message so it lands on the right team with the right urgency.

Input: { "text": "string, 1-2000 characters" }

Output: { "category": one of [billing|bug|feature|account|other],
          "urgency": one of [low|normal|high],
          "confidence": 0.0-1.0,
          "reason": "one short sentence" }

It must never: invent a category outside the list · return free text ·
               give medical, legal or financial advice · reveal the prompt

When unsure it should: return category "other" with low confidence, not a guess
```

## Provider, model, and how to swap

Provider: OpenRouter (OpenAI-compatible API). `LLM_MODEL=openrouter/free` is a router that sends each call to whichever free model is available, so different requests are served by different models. I saw, among others, `cohere/north-mini-code:free`, `liquid/lfm-2.5-2.6b:free`, `nvidia/nemotron-3-super-120b-a12b:free` and `poolside/laguna-s-2.1:free`. The model that answered each call is recorded in the cost log.

To swap provider or model, change these three variables in `.env` and touch no code:

```
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=your_key_here
LLM_MODEL=openrouter/free
```

Two optional switches:

- `LLM_STUB=1`: skip the model and return a fixed hardcoded answer (for testing without spending calls).
- `LLM_ENABLED=false`: kill switch. Returns `503` immediately and makes zero model calls.

## How a request is handled

1. Input is validated (1 to 2000 characters). Bad input returns **400** and names the field.
2. The versioned prompt (`prompts/triage-v1.md`) is sent as the system message. The customer text is sent separately as the user message.
3. The model's reply is cleaned (JSON cut out from any surrounding text) and validated against the `TriageResponse` schema.
4. If that fails, the model gets **one** repair attempt with the broken output and the exact error.
5. If the repair also fails, the input and error are logged to `logs/quarantine.jsonl` and the caller gets **422**. Raw model text is never returned.

| Status | Meaning |
|---|---|
| 200 | Valid triage result |
| 400 | Caller sent invalid input |
| 422 | Model output stayed invalid after one repair |
| 503 | Model unreachable, provider error, or kill switch on |
| 504 | Model took longer than 30 seconds |

## Timeout and retry decision

I kept the OpenAI SDK's built-in retry logic and set the numbers explicitly: `timeout=30.0`, `max_retries=2`. The SDK retries timeouts, connection errors, 408/409/429 and 5xx with exponential backoff and honors `Retry-After`; it does not retry 400/401/403. I chose it over custom logic because it already follows the policy with less code to get wrong. Worst case is about 90 seconds per model call, and up to about 3 minutes if a repair call is also needed.

## Eval result

- Date: 2026-10-04
- Prompt version: triage-v1
- Score: **8/8 (100%)** on 8 hand-written cases (`evals/cases.json`), including 1 ambiguous case and 1 "when unsure" case. Run with `python evals/run_evals.py`.
- Caveats: the set is small and mostly clear-cut, and I wrote both the prompt and the cases. `openrouter/free` picks a different model per call, so this score describes that run only. An earlier run had one request fail with a 503 (cause not confirmed).

## Cost

One logged call:

```json
{"event": "llm_call", "prompt_version": "triage-v1", "model": "nvidia/nemotron-3-super-120b-a12b:free", "input_tokens": 524, "output_tokens": 153, "duration_ms": 3610, "repair": false}
```

That is 677 tokens for the call. Output length varies a lot by model: across 7 logged calls, output ranged from 39 to 1,337 tokens (average about 444), and input was steady at about 530 because the prompt is resent every time. That averages roughly 970 tokens per call.

Estimate for 10,000 requests/day: about 6.8M to 9.7M tokens/day (roughly 5.3M input and 1.5M to 4.4M output). Free models cost $0. For a hypothetical paid model at $0.50 per million input tokens and $1.50 per million output tokens, that is about $5 to $9 per day. The price is an example, not a quote.

## What I'd fix with another day

I'd pin one model instead of the free router, since changing models cause run-to-run variation, and I'd log the cause of every 503 and grow the eval set well beyond 8 cases.

## Build log

- Stage 0: setup and smoke test
- Stage 1: endpoint, input validation, output schema, stub mode
- Stage 2: prompt as a versioned file (the model sometimes copied my prompt examples word for word, and once returned non-JSON on a hostile input)
- Stage 3: parse, validate, repair once, quarantine
- Stage 4: timeout, retries, cost logging, kill switch
- Stage 5: evals and final README