import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from schemas import TriageRequest, TriageResponse
from openai import OpenAI
from parsing import parse_triage
from pydantic import ValidationError
from quarantine import quarantine

load_dotenv()

client = OpenAI(
    base_url=os.environ["LLM_BASE_URL"],
    api_key=os.environ["LLM_API_KEY"],
)

app = FastAPI()
PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "triage-v1.md")

with open(PROMPT_PATH, encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


def call_model(messages):
    response = client.chat.completions.create(
        model=os.environ["LLM_MODEL"],
        temperature=0.2,
        messages=messages,
    )
    return response.choices[0].message.content


@app.post("/triage", response_model=TriageResponse)
def triage(req: TriageRequest):
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
        text2 = call_model(repair_messages)
        try:
            return parse_triage(text2)
        except (ValueError, ValidationError) as e2:
            print("REPAIR FAILED:", e2)
            quarantine(req.text, e2, "triage-v1")
            raise HTTPException(status_code=422, detail="Model returned invalid output")


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors()},
    )