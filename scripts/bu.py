import asyncio

from browser_use import Agent, ChatOllama, ChatGoogle
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

async def main():
    promptFile = "../prompts/task1.txt"
    with open(promptFile, "r") as f:
        task = f.read()

    llm = ChatGoogle(model='gemini-3.5-flash-lite')
    agent = Agent(
        task=task,
        llm=llm,
        llm_timeout=600,
        step_timeout=600,
        use_vision=False,
    )
    history = await agent.run()
    print(history.final_result())
    
    with open("../outputs/" + promptFile + "BUOutput" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".txt", "w") as f:
        f.write(str(history.final_result()))

if __name__ == "__main__":
    asyncio.run(main())