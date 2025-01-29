from fastapi import FastAPI, HTTPException
import requests
from pydantic import BaseModel
import re

# Initialize FastAPI app
app = FastAPI()

# Hardcoded Mistral AI API key (NOT RECOMMENDED)
MISTRAL_API_KEY = "aMsz4jReS4h6DvDoiUhsljjv2HjOYbgw"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

# Request model
class GoalRequest(BaseModel):
    goal: str

def call_mistral_api(goal):
    """Calls the Mistral AI API and returns the response."""
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "model": "mistral-medium",
        "messages": [{"role": "user", "content": f"Break down the goal into daily tasks: {goal}"}],
    }

    response = requests.post(MISTRAL_API_URL, headers=headers, json=data)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"Error: {response.text}")

    return response.json()

def parse_tasks(content: str):
    """Parses the AI response into a structured JSON format."""
    tasks = []
    current_task = None

    lines = content.split("\n")
    
    for line in lines:
        line = line.strip()

        # Detect tasks using regex
        task_match = re.match(r"\*\s?Task\s?\d+:(.*)", line)
        subtask_match = re.match(r"\+\s?Subtask\s?\d+\.\d+:(.*)", line)

        if task_match:
            if current_task:
                tasks.append(current_task)
            current_task = {"task": task_match.group(1).strip(), "subtasks": []}

        elif subtask_match and current_task:
            current_task["subtasks"].append(subtask_match.group(1).strip())

    if current_task:
        tasks.append(current_task)

    return tasks

@app.post("/generate_tasks/")
async def generate_tasks(request: GoalRequest):
    ai_response = call_mistral_api(request.goal)

    print("RAW AI RESPONSE:\n", ai_response)  # Debugging step

    if "choices" not in ai_response or not ai_response["choices"]:
        raise HTTPException(status_code=500, detail="Invalid response from AI")

    ai_text = ai_response["choices"][0]["message"]["content"]  # Extract AI response content

    tasks = parse_tasks(ai_text)

    return {"goal": request.goal, "tasks": tasks}
