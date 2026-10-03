import json
from schemas import TriageResponse

def extract_json(text):
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in model output")

    cut = text[start:end + 1]
    return json.loads(cut)

def parse_triage(text):
    data = extract_json(text)
    # TODO: validate data against TriageResponse and return the result
    response = TriageResponse.model_validate(data)
    return response

