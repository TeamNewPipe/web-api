from flask_caching import Cache
from quart import Blueprint

# using the app factory pattern, which means these are imported/initialized in a factory function
bp = Blueprint(__name__, "bp")


# initialize cache, making sure that the values won't expire in a practical amount of time
# using an absurdly high value is a bad solution, and the extension should just support that, but the author
# indicated that they don't want to do that
# see https://github.com/sh4nks/flask-caching/issues/183 for more information
# simple cache means in-memory, which avoids unnecessary disk I/O and simplifies debugging
# also, it works well when synchronizing the requests as we do to avoid third-party API rate limits
cache = Cache(with_jinja2_ext=False, config={
    "CACHE_TYPE": "simple",
    "CACHE_DEFAULT_TIMEOUT": 2**31,
})


# must import these after creating bp/cache
# note we don't have to import anything in particular; importing just the views will do
from . import views  # noqa: E402 F401

# must be imported last for obvious reasons
from .app import make_app  # noqa: E402


# let users auto-import only make_app
__all__ = (make_app,)
