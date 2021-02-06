from flask_caching import Cache
from quart import Blueprint

# using the app factory pattern, which means these are imported/initialized in a factory function
bp = Blueprint(__name__, "bp")
cache = Cache(with_jinja2_ext=False, config={"CACHE_TYPE": "simple"})


# must import these after creating bp/cache
# note we don't have to import anything in particular; importing just the views will do
from . import views  # noqa: E402 F401

# must be imported last for obvious reasons
from .app import make_app  # noqa: E402


# let users auto-import only make_app
__all__ = (make_app,)
