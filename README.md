# AI-Code-Context-Reviewer
Automated code review bot using AI.

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
## Features
* Reviews based on Ruleset defined in `rules.txt`
* Simple Deployment via Vercel

## Tools/Libraries
* Groq
* Fastapi
* Vercel (for Deployement url)