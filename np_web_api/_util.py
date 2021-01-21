import aiohttp


async def fetch_text(url: str):
    headers = {
        "user-agent": "",
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            return await response.text()