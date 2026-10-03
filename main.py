import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from schemas import TriageRequest, TriageResponse
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url = os.environ["LLM_BASE_URL"],
    api_key=os.environ["LLM_API_KEY"],
)

app = FastAPI()
PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "triage-v1.md")

with open(PROMPT_PATH, encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

@app.post("/triage")
def triage(req: TriageRequest):
    if os.environ.get("LLM_STUB") == "1":
        return {"category": "billing", "urgency": "low", "confidence": 0.83, "reason": "stub answer"}

    response = client.chat.completions.create(
        model=os.environ["LLM_MODEL"],
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": req.text},
        ],
    )
    return {"raw": response.choices[0].message.content, "model": response.model}

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors()},
    )