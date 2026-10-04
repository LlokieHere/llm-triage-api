import json
import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from openai import (
    OpenAI,
    APITimeoutError,
    APIConnectionError,
    AuthenticationError,
    APIStatusError,
)
from pydantic import ValidationError

from parsing import parse_triage
from quarantine import quarantine
from schemas import TriageRequest, TriageResponse

load_dotenv()

PROMPT_VERSION = "triage-v1"

# Decision: keep the SDK's retry logic (retries timeouts, connection errors,
# 408/409/429/5xx with exponential backoff + jitter and Retry-After;
# never retries 400/401/403), but set the numbers explicitly.
client = OpenAI(
    base_url=os.environ["LLM_BASE_URL"],
    api_key=os.environ["LLM_API_KEY"],
    timeout=30.0,
    max_retries=2,
)

app = FastAPI()

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", f"{PROMPT_VERSION}.md")
with open(PROMPT_PATH, encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


def log_call(model, usage, duration_ms, repair):
    """One structured log line per model call."""
    print(json.dumps({
        "event": "llm_call",
        "prompt_version": PROMPT_VERSION,
        "model": model,
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
        "duration_ms": duration_ms,
        "repair": repair,
    }))


def call_model(messages, repair=False):
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=os.environ["LLM_MODEL"],
            temperature=0.2,
            messages=messages,
        )
    except APITimeoutError:
        raise HTTPException(status_code=504, detail="The model took too long to respond")
    except APIConnectionError:
        raise HTTPException(status_code=503, detail="Could not reach the model")
    except AuthenticationError:
        print("PROVIDER AUTH FAILED: check LLM_API_KEY")
        raise HTTPException(status_code=503, detail="Model service is misconfigured")
    except APIStatusError as e:
        print("PROVIDER ERROR:", e.status_code)
        raise HTTPException(status_code=503, detail="Model service is unavailable")

    duration_ms = int((time.time() - start) * 1000)
    log_call(response.model, response.usage, duration_ms, repair)
    return response.choices[0].message.content or ""


@app.post("/triage", response_model=TriageResponse)
def triage(req: TriageRequest):
    # Kill switch: no model call at all.
    if os.environ.get("LLM_ENABLED", "true").lower() == "false":
        raise HTTPException(status_code=503, detail="Triage is temporarily disabled")

    if os.environ.get("LLM_STUB") == "1":
        return {"category": "billing", "urgency": "low", "confidence": 0.83, "reason": "stub answer"}

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": req.text},
    ]
    text = call_model(messages)

    try:
        return parse_triage(text)
    except (ValueError, ValidationError) as e:
        print("PARSE FAILED:", e)
        repair_messages = messages + [
            {"role": "assistant", "content": text},
            {"role": "user", "content": f"Your reply was invalid: {e}. Reply with corrected JSON only."},
        ]
        text2 = call_model(repair_messages, repair=True)
        try:
            return parse_triage(text2)
        except (ValueError, ValidationError) as e2:
            print("REPAIR FAILED:", e2)
            quarantine(req.text, e2, PROMPT_VERSION)
            raise HTTPException(status_code=422, detail="Model returned invalid output")


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"detail": exc.errors()})