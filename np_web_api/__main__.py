import asyncio
import logging

from . import make_app
from ._logging import configure_logging


def main():
    # set up logging once
    configure_logging(logging.DEBUG)

    app = make_app(debug=True)

    # note: we must specifically pass the event loop we want to use to avoid issues with futures from other loops in
    # the synchronization in the views module
    # https://stackoverflow.com/a/56704621
    loop = asyncio.get_event_loop()

    # always run in debug mode, if launched directly
    app.run(debug=True, loop=loop)


main()
