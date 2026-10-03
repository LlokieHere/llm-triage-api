import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from schemas import TriageRequest, TriageResponse

load_dotenv()
app = FastAPI()

@app.post("/triage", response_model=TriageResponse)
def triage(req: TriageRequest):
    if os.environ.get("LLM_STUB") == "1":
        return {"category": "billing", "urgency": "low", "confidence": 0.83, "reason": "stub answer"}
        
    raise HTTPException(status_code=501, detail="Model not connected yet")

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors()},
    )