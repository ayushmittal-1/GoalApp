from fastapi import FastAPI
import re
import requests
from pydantic import BaseModel
import json
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


#  Hardcoded API Key (Not Secure – Use Environment Variables Instead)
MISTRAL_API_KEY = "8ouOddJYIgTdILvYVFPyw7qSj6c0zjzL"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

class GoalRequest(BaseModel):
    goal: str

def extract_days(goal: str) -> int:
    """Extracts the number of days from the input goal text."""
    match = re.search(r"(\d+)\s*(day|week|month|year)s?", goal, re.IGNORECASE)
    if match:
        num = int(match.group(1))
        unit = match.group(2).lower()
        if unit == "week":
            return num * 7
        elif unit == "month":
            return num * 30
        elif unit == "year":
            return num * 365
        return num
    return 30  # Default to 30 days if no duration is found

@app.post("/generate_tasks/")
async def generate_tasks(request: GoalRequest):
    num_days = extract_days(request.goal)

    prompt = (
    f"Break down the following goal into exactly {num_days} daily tasks. "
    "Each day should focus on a different DSA topic, covering concepts, examples, and practice. "
    "Topics should progress from basic (arrays, linked lists) to advanced (dynamic programming, graphs). "
    "Ensure diversity in learning approaches: some days focus on theory, others on coding practice. "
    "Respond in JSON format like this: { 'tasks': [ 'Day 1: Learn Arrays, do 5 problems', 'Day 2: Learn Recursion, solve 3 problems' ] } "
    f"Goal: {request.goal}"
)


    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "mistral-medium",
        "messages": [{"role": "user", "content": prompt}],
    }

    response = requests.post(MISTRAL_API_URL, headers=headers, json=payload)
    
    if response.status_code != 200:
        return {"error": "Failed to fetch response from Mistral AI", "status_code": response.status_code}

    ai_response = response.json()
    print("\n RAW AI RESPONSE:\n", ai_response)  # Debugging: Print the full response

    content = ai_response.get("choices", [{}])[0].get("message", {}).get("content", "")

    print("\n Extracted Content:\n", content)  # Debugging: Print extracted content

    tasks = parse_tasks(content)

    return {"goal": request.goal, "tasks": tasks}

def parse_tasks(content: str):
    """Parses the AI response into a structured JSON format."""
    tasks = []
    
    try:
        # Try parsing directly as JSON
        parsed_data = json.loads(content)
        if isinstance(parsed_data, list):
            return parsed_data  # If Mistral directly gives a list, return it
        
    except json.JSONDecodeError:
        print("\n JSON Parsing Failed. Trying to extract numbered tasks.")

    # Otherwise, extract manually
    lines = content.split("\n")
    for line in lines:
        line = line.strip()
        match = re.match(r"^\d+\.\s*(.+)", line)  # Matches "1. Task description"
        if match:
            tasks.append({"task": match.group(1).strip(), "subtasks": []})

    return tasks
