from datetime import datetime

import aiohttp


class RateLimitExceededError(Exception):
    def __init__(self, response: aiohttp.ClientResponse):
        self.response = response

    def __str__(self):
        parsed_reset = None
        reset = None

        try:
            reset = self.response.headers["x-ratelimit-reset"]
        except KeyError:
            pass

        if reset is not None:
            try:
                parsed_reset = datetime.fromtimestamp(float(reset))
            except (ValueError, TypeError):
                pass

        if not reset:
            reset_msg = "unknown"
        elif not parsed_reset:
            reset_msg = reset
        else:
            reset_msg = f"{parsed_reset} ({reset})"

        return f"{self.response.url}: rate limit exceeded, reset: {reset_msg}"


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
