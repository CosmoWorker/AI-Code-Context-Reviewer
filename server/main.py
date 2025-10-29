from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os, logging, requests
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
app=FastAPI()
app.add_middleware(CORSMiddleware)

logger=logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

github_token=os.getenv("GITHUB_PAT_TOKEN")
client=Groq(api_key=os.getenv("GROQ_API_KEY"))

@app.get("/")
def main():
    return {"msg":"Hello from code reviewer server"}

'''
Abstract Response object 
{
  "action": "",
  "number": "",
  "pull_request": {},
  "repository": {},
  "sender": {}
}
'''
@app.post("/webhook") # endpoint for gh webhhook
def handle_pr_event(payload: dict):
    pr_response=payload["pull_request"]
    if (pr_response["state"] == "open"):
        try:
            logger.info("Reading Rules File")
            with open("rules.txt", "r") as f:
                ruleset=f.read()
        except Exception as e:
            logger.error("Error reading  rules file: ", e)
        system_prompt=f"""
            You are an AI Code Reviewer. You should Review the git diff provided based on the ruleset & other facets like issues description (if provided), etc.
            Rules: 
            {ruleset}
            Group the issues by file & clearly format them as per file with description if necessary.
            Do not suggest unrelated issues nor add add any fluff. 
            Format:
            ### <Title (with Issue if any)>
            #### <filename>
        """
        headers={"Authorization": f"Bearer {github_token}", "X-GitHub-Api-Version": "2022-11-28"}
        diffs=requests.get( pr_response["diff_url"], headers=headers).text
        user_prompt=f"""
            Diff:
            {diffs}
        """
        chat_completion=client.chat.completions.create(
            messages=[
                {
                    "role":"system",
                    "content":system_prompt
                },
                {
                    "role":"user",
                    "content":user_prompt
                }
            ],
            model="openai/gpt-oss-120b"
        )
        response=chat_completion.choices[0].message.content
        data={
            "body": f'''{response}'''
        }
        requests.post(pr_response["comments_url"], json=data,headers=headers)

    return {"msg":"Check Done"}

if __name__ == "__main__":
    main()
