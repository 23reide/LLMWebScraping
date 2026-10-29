import asyncio
import os

from skyvern import Skyvern


async def main():
    skyvern = Skyvern.local()

    result = await skyvern.run_task(
        prompt="Get the title and points of the #1 post",
        url="https://news.ycombinator.com",
        data_extraction_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title of the top post"},
                "points": {"type": "integer", "description": "Points of the top post"},
            },
        },
        wait_for_completion=True,
    )

    print(f"Status: {result.status}")
    print(f"Output: {result.output}")
    print(f"View run: {result.app_url}")


asyncio.run(main())