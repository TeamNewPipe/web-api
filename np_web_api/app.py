import os

import sentry_sdk
from quart import Quart
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

from . import cache, bp
from ._logging import configure_logging


def make_app(debug: bool = False):
    app = Quart(__name__)

    cache.init_app(app)
    sentry_url = os.environ.get("SENTRY_URL", None)

    # register views
    app.register_blueprint(bp)

    if not debug and sentry_url:
        print("Setting up Sentry integration")
        sentry_sdk.init(dsn=sentry_url)

        app = SentryAsgiMiddleware(app)

    return app


def make_production_app():
    """
    Configure logging before creating the application. Useful with application servers, where it's pretty impossible to
    run code other than the app factory.
    :return: standard app created by make_app
    """

    configure_logging()

    return make_app()
