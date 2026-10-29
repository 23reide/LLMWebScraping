# LLM Tools

`bu.py` contains BrowserUse script (requires .env setup)
```
# .env file
GOOGLE_API_KEY=your_free_tier_api_key
```

`sky_vern.py` contains SkyVern script (requires .env setup)
```
# .env file
ENABLE_OLLAMA=true
LLM_KEY=OLLAMA
OLLAMA_MODEL=llama3.2
OLLAMA_SERVER_URL=http://127.0.0.1:11434
OLLAMA_SUPPORTS_VISION=false
```

`stagehand.ts` contains Stagehand script
>(Stagehand can only use different models if written in TypeScript, hence the .ts file and package json files.)

# Prompts

`task1.txt` - first draft prompt

`task1buOutput.txt` - output from feeding `task1.txt` to BrowserUse