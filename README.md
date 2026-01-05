# AI-Code-Context-Reviewer
An automated code reviewer that reviews & summarizes Pull Requests.

## Tools / Libraries
* FastAPI 
* Groq 
* Github Webhook API Gateway + REST APIs
* Vercel (Serverless Deployment)

## Python Dependency Management ( using `uv` )
Install `uv`: ( official site: [uv Installation Reference↗](https://docs.astral.sh/uv/getting-started/installation/)) 
```ruby
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Install dependencies (app with `pyproject.toml`):
```bash
cd $server
uv install
```

## Current Setup / Installation
To use the reviewer with the repository:
1.  Create a GitHub webhook for the repository

    *   Go to Repository → Settings → Webhooks

    * Add a new webhook

    * Set Payload URL to the deployed webhook endpoint

    * Content type: application/json

    * Select individual events: Pull requests & Issue comments
2. Open a Pull request
    * A structured summary will be automatically generated.
3. Comment `/review` on a Pull request
    * Inline review comments will be generated on the PR diff.

**Note: Currently ruleset is generalized & applied uniformly across all repositories.** 