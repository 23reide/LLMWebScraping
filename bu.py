import asyncio

from browser_use import Agent, ChatOllama, ChatGoogle
from dotenv import load_dotenv

load_dotenv()

async def main():
    with open("task1.txt", "r") as f:
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

if __name__ == "__main__":
    asyncio.run(main())