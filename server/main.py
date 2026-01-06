from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
import requests
import base64
import re
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
app = FastAPI()
app.add_middleware(CORSMiddleware)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

github_token = os.getenv("GITHUB_PAT_TOKEN")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


@app.get("/")
def main():
    return {"msg": "Hello from code reviewer server"}


"""
Webhook Abstract Response object for pull requests
{
  "action": "",
  "number": "",
  "pull_request": {},
  "repository": {},
  "sender": {}
}
"""
headers = {
    "Authorization": f"Bearer {github_token}",
    "X-GitHub-Api-Version": "2022-11-28",
}


def extract_old_filecontent_diff(diffs: str, base_sha: str) -> str:
    logger.info("Extracting filenames from diffs...")
    diffs_txt = diffs.split("diff --git")
    diff_filepaths = []
    for i in diffs_txt[1:]:
        old_fileline = next(
            (line for line in i.splitlines() if line.startswith("--- ")), None
        )
        if not old_fileline or old_fileline.startswith("--- /dev/null"):
            continue

        diff_filepaths.append(old_fileline.replace("--- a/", "").strip())
    logger.info("Old Filenames extracted from BASE")
    base_filecontent = """"""
    for path in diff_filepaths:
        contents_url = f"https://api.github.com/repos/CosmoWorker/AI-Code-Context-Reviewer/contents/{path}?ref={base_sha}"
        content_obj = requests.get(contents_url, headers=headers).json()
        base_filecontent += content_obj["path"] + "\n"
        base_filecontent += base64.b64decode(content_obj["content"]).decode() + "\n"
    logger.info("base files content decoded")
    return base_filecontent


def hunks_per_diff(diffs: str):
    diffs_lines = diffs.splitlines()

    file_hunks = {}  # {"server/a.py": {"Hunk 1":{'old': (10, 2), 'new': (16,7)}, ...}}
    current_file = None
    hunk_index = 1

    # regex to get filenames and hunk lines
    file_regex = re.compile(r"diff --git a/(.+?) b/(.+)")
    hunk_regex = re.compile(r"@@\s*-\s*(\d+)(?:,(\d+))?\s+\+\s*(\d+)(?:,(\d+))?\s*@@")

    i = 0
    while i < len(diffs_lines):
        line = diffs_lines[i]

        m = file_regex.match(line)
        if m:
            current_file = m.group(1)  # always use "a/<file>"
            file_hunks[current_file] = {}
            hunk_index = 1
            i += 1
            continue

        if line.startswith("@@") and current_file:
            diffs_lines.insert(i, f"Hunk {hunk_index}: ")

            m = hunk_regex.match(line)
            if m:
                old_start = int(m.group(1))
                old_count = int(m.group(2) or 1)
                new_start = int(m.group(3))
                new_count = int(m.group(4) or 1)

                file_hunks[current_file][f"Hunk {hunk_index}"] = {
                    "old": (old_start, old_count),
                    "new": (new_start, new_count),
                }

            hunk_index += 1
            i += 1  # skip inserted line
        i += 1

    return "\n".join(diffs_lines), file_hunks


"""
{
    "server/file.py":{
        1 : {"review":True, "text":"..."},
        2 : {"review": False, "text": ""},
    },
}
"""


def parse_llm_response(res_txt: str) -> dict:
    result = {}
    curr_file = curr_hunk = None
    for line in res_txt.splitlines():
        line = line.strip()
        if line.startswith("####"):
            curr_file = line[5:].strip()
            result[curr_file] = {}
        elif line.startswith("Hunk"):
            m = re.match(r"Hunk\s+(\d+)\s*Review:\s*(Yes|No)", line, re.IGNORECASE)
            if m:
                hunk_num = int(m.group(1))
                needs_review = m.group(2) == "Yes"
                result[curr_file][hunk_num] = {"review": needs_review, "text": ""}
                curr_hunk = hunk_num

        elif line.startswith("Review"):
            m = re.match(r'Review:\s*"(.*)"', line)
            if m:
                result[curr_file][curr_hunk]["text"] = m.group(1)
    return result


@app.post("/webhook")  # endpoint for gh webhhook
def handle_pr_event(payload: dict, x_github_event: str = Header(None)):
    if x_github_event == "issue_comment":
        if payload["issue"]["pull_request"] and payload["comment"]["body"] == "/review":
            pr_url = payload["issue"]["pull_request"]["url"]
            logger.info("PR URL from issue_comment payload: ", pr_url)
            pr_info = requests.get(pr_url, headers=headers).json()
            logger.info("Getting PR info...")
            if pr_info["state"] == "open":
                try:
                    logger.info("Reading Rules File")
                    with open("rules.txt", "r") as f:
                        ruleset = f.read()
                except Exception as e:
                    logger.error("Error reading  rules file: ", e)

                system_prompt = f"""
                    You are an Professional Code Reviewer. You review/comment the git diff provided based on the ruleset & other facets like issues description (if provided), etc.
                    Rules: 
                    {ruleset}
                    Group the issues by file & clearly format them. The context provided from base files is only for cross referencing the diffs to avoid inaccurate comments like unused imports, no instance, etc.
                    Do not suggest unrelated issues nor add add any fluff & be concise logically with comment/review with minor suggestion (with example) only if required. Provide review/comment for atleast one.
                    STRICT FORMAT RULES — MUST FOLLOW EXACTLY:
                    For each file:
                    #### <filename>
                    Hunk <number> Review: Yes|No
                    Review: "<text>"
                    - DO NOT skip any hunk.
                    - DO NOT change capitalization & add extra markers.
                    - DO NOT include explanation outside the format or the Hunks.
                    - If no review needed, write:
                        Hunk <n> Review: No
                        Review: ""
                """
                logger.info("Sending a diff request...")
                diffs = requests.get(pr_info["diff_url"], headers=headers).text
                logger.info("Received diff")
                base_commit_filecontent = extract_old_filecontent_diff(
                    diffs, pr_info["base"]["sha"]
                )
                logger.info("Base commit file received")
                hunks_diff = hunks_per_diff(diffs)
                logger.info(f"HUnks diff response: {hunks_diff}")
                user_prompt = f"""
                    Context(Base commit Files):
                    {base_commit_filecontent}
                    Diff:
                    {hunks_diff[0]}
                """
                logger.info("Calling groq API model...")
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    model="openai/gpt-oss-120b",
                )
            response = chat_completion.choices[0].message.content
            logger.info(f"Response received from LLM: {response}")

            parsed_response = parse_llm_response(response)
            logger.info("Parsed LLM response for review body content")
            logger.info(f"Parsed response: {parsed_response}")
            hunks = hunks_diff[1]
            commit_id = pr_info["head"]["sha"]
            for filename, hunks_data in parsed_response.items():
                for hunks_num, info in hunks_data.items():
                    if filename not in hunks:
                        logger.info(
                            f"Filename {filename} not found in parsed diff hunks.."
                        )
                        continue

                    if not info["review"]:
                        logger.info(f"No review/comment for {filename}")
                        continue
                    text = info["text"]
                    old_start, old_count = hunks[filename][f"Hunk {hunks_num}"]["old"]
                    new_start, new_count = hunks[filename][f"Hunk {hunks_num}"]["new"]

                    if new_count > 0:
                        side = "RIGHT"
                        start_line = new_start
                        end_line = new_start + new_count - 1
                    else:
                        side = "LEFT"
                        start_line = old_start
                        end_line = old_start + old_count - 1

                    payload = {
                        "body": text,
                        "commit_id": commit_id,
                        "path": filename,
                        "start_side": side,
                        "start_line": start_line,
                        "line": end_line,
                        "side": side,
                    }
                    logger.info(f"Posting comment for {filename}'s PR diff.")
                    requests.post(
                        pr_info["review_comments_url"], json=payload, headers=headers
                    )

            return {"msg": "Review Check Done"}

    elif x_github_event == "pull_request":
        pr_response = payload["pull_request"]
        logger.info("Received Github PR event")

        if pr_response["action"] == "opened":
            system_prompt = """You are an Code Summarizer to help Maintainers/Reviewers. Based on the diffs and context provided by the Pull request with additional details,
                you summarize what the PR is about with formatted description if necessary. Changes would be in a table format & related files can be grouped.
                Based on additional context such as code structure & repository file tree, you generate a Mermaid diagram code which aligns with it only if codebase structure is provided or is accurately understood.
                Some example format: (Can be modified as per summarization need)
                ### Title 
                <Concise Description>
                #### Changes
                Files     | Summary 
                --------- | ---------
                <`files`> | <content>
                <`files`> | <content>

                Example Format for mermaid diagram:
                ```mermaid
                flowchart TD
                    A[Christmas] -->|Get money| B(Go shopping)
                    B --> C{Let me think}
                    C -->|One| D[Laptop]
                    C -->|Two| E[iPhone]
                    C -->|Three| F[fa:fa-car Car]
                ```
            """

            logger.info("Sending a diff request...")
            diffs = requests.get(pr_response["diff_url"], headers=headers).text
            logger.info("Received diff")
            base_commit_filecontent = extract_old_filecontent_diff(
                diffs, pr_response["base"]["sha"]
            )
            logger.info("Base commit file received")
            hunks_diff = hunks_per_diff(diffs)
            logger.info(f"Hunks diff response: {hunks_diff}")
            user_prompt = f"""
                Context(Base commit Files):
                {base_commit_filecontent}
                Diff:
                {hunks_diff[0]}
            """
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model="openai/gpt-oss-120b",
            )
            response = chat_completion.choices[0].message.content
            logger.info("Response received from LLM")
            data = {"body": f"""{response}"""}
            requests.post(pr_response["comments_url"], json=data, headers=headers)

            return {"msg": "Summary Done"}

    else:
        logger.info("Ignored - not PR nor Issue Comment event")
        return {"msg": "Ignored - Not a PR/issue-comment event"}


# @app.post("/webhook-comment")  # some other endpoint name
# def handle_issue_comment_event():
#     pass


if __name__ == "__main__":
    main()
