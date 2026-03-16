import asyncio
import uuid

from dotenv import load_dotenv

load_dotenv()

from server import _run_agent_stream  # noqa: E402


async def main():
    message = "Critique this design"
    figma_url = "https://www.figma.com/design/sYQZuNXBJVIoPWM7onzmx/ClimatePulse?node-id=11-5&t=GEBwxAwDedxCw5dz-1"
    session_id = str(uuid.uuid4())

    try:
        async for event in _run_agent_stream(session_id, "test_user", message, figma_url):
            print(event, end="")
    except Exception:
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
