# UI

## Access Hosted UI:

Hosted at: https://llmwebscraping-ddc.streamlit.app/

Hosting relies on Streamlit cloud environment (free) and [Browserbase](https://www.browserbase.com/orgs/jtqrdos3gsga/45a513f9-edb8-4899-a3bf-e5be370217eb/home) remote browser API (free but very limited to 1 hour / month)

Hosting also relies on a Gemini API key.

Either API key can be swapped out in the Streamlit hosting settings.

## Start UI Locally:

```
# Run from project root
steamlit run app.py
```

`app.py` holds a Streamlit app.

`prompt_store.py` holds the logic for adding/deleting/editing prompts from the UI.


# Prompts

Prompts used by UI are in `/prompts` (task1.txt is not used by UI)

Outputs from UI run script are in `./outputs` along with the prompt used in the last run `_lastTask.txt`.

`task1.txt` - first draft prompt

`task1buOutput.txt` - output from feeding `task1.txt` to BrowserUse

# LLM Tools in `/scripts`

[Tool evaluation notes](https://vanderbilt365-my.sharepoint.com/:w:/g/personal/emma_reid_vanderbilt_edu/IQC4NBQ6WMCjS47Cl8g_aCLXAa_YP7-nLkHJ092Zw24L0iY?e=U9ISvg)

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

# Other Project Docs

[Informal project notes](https://vanderbilt365-my.sharepoint.com/:w:/g/personal/emma_reid_vanderbilt_edu/IQDJqkImELljTISCwKXPm3NNAavd9nbYxQfL0duw6xS7d4c?e=5xcUfM)

[Overleaf project](https://www.overleaf.com/project/6abfc789e05a6864e22e68c1)