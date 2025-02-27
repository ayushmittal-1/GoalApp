from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os

from fastapi import FastAPI, HTTPException
import re
import requests
from pydantic import BaseModel
import json
from fastapi.middleware.cors import CORSMiddleware


# MongoDB Connection URI (Replace with your MongoDB URL)
MONGO_URI = "mongodb://localhost:27017"
DATABASE_NAME = "goal_tracker"

client = AsyncIOMotorClient(MONGO_URI)
db = client[DATABASE_NAME]
users_collection = db["users"]  # Collection to store user data




app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Hardcoded API Key (Not Secure – Use Environment Variables Instead)
MISTRAL_API_KEY = "8ouOddJYIgTdILvYVFPyw7qSj6c0zjzL"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

class GoalRequest(BaseModel):
    user_id: str #unique identifier for user
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
        "Each day should focus on a different topic, covering concepts, and practice. "
        "Topics should progress from basic to advanced . "
        "Ensure diversity in learning approaches: some days focus on theory, others on practice. "
        "Respond in JSON format like this: { \"tasks\": [ \"Day 1: learn basics of whatever skill is asked,\", \"Day 2: practice that skill, practice\" ] } "
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
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch response from Mistral AI")

    ai_response = response.json()
    print("\n RAW AI RESPONSE:\n", ai_response)  # Debugging: Print the full response

    content = ai_response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    print("\n Extracted Content:\n", content)  # Debugging: Print extracted content

    tasks = parse_tasks(content)

    if not tasks:
        raise HTTPException(status_code=400, detail="Failed to extract tasks from response")
    
    # Store in MongoDB
    task_entry = {
        "user_id": request.user_id,
        "goal": request.goal,
        "tasks": tasks,
    }
    result = await users_collection.insert_one(task_entry)

    return {"goal": request.goal, "tasks": tasks, "task_id": str(result.inserted_id)}

def parse_tasks(content: str):
    """Parses the AI response into a structured JSON format."""
    tasks = []

    try:
        # Try parsing directly as JSON
        parsed_data = json.loads(content)
        if isinstance(parsed_data, dict) and "tasks" in parsed_data:
            return parsed_data["tasks"]  # If Mistral directly gives a JSON response
        elif isinstance(parsed_data, list):
            return parsed_data  # If Mistral directly gives a list of tasks
    except json.JSONDecodeError:
        print("\n JSON Parsing Failed. Trying to extract numbered tasks.")

    # Otherwise, extract manually from numbered format
    lines = content.split("\n")
    for line in lines:
        line = line.strip()
        match = re.match(r"^\s*Day\s*\d+:\s*(.+)", line)  # Matches "Day X: Task description"
        if match:
            tasks.append(match.group(1).strip())

    return tasks






@app.get("/user_tasks/{user_id}")
async def get_user_tasks(user_id: str):
    tasks = await users_collection.find({"user_id": user_id}).to_list(100)
    for task in tasks:
        task["_id"] = str(task["_id"])  # Convert ObjectId to string
    return tasks
