from datetime import datetime

import aiohttp


class RateLimitExceededError(Exception):
    def __init__(self, response: aiohttp.ClientResponse):
        self.response = response

    def __str__(self):
        try:
            reset = self.response.headers["x-ratelimit-reset"]
        except KeyError:
            reset = None
        else:
            try:
                reset = datetime.fromtimestamp(float(reset))
            except (ValueError, TypeError):
                pass

        if not reset:
            reset = "unknown"

        return f"{self.response.url}: rate limit exceeded, reset: {reset}"


async def fetch_text(url: str):
    headers = {
        "user-agent": "",
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            # special treatment for rate limit issues
            if response.status == 429:
                raise RateLimitExceededError(response)

            # raise an exception if the status is not 200
            response.raise_for_status()

            return await response.text()
