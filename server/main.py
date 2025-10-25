from fastapi import FastAPI
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
app=FastAPI()
github_token=os.getenv("GITHUB_PAT_TOKEN")
client=Groq(api_key=os.getenv("GROQ_API_KEY"))

@app.get("/")
def main():
    print("Hello from Code reviewer server!")

@app.post("/webhook") # endpoint for gh webhhook
def handle_pr_event(payload: dict):
    pass

if __name__ == "__main__":
    main()
