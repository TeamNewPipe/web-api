import os

import sentry_sdk
from quart import Quart
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

from . import cache, bp


def make_app(debug: bool = False):
    app = Quart(__name__)

    # init Quart/Flask extensions
    cache.init_app(app)

    # register views
    app.register_blueprint(bp)

    # enable Sentry integration, if the user provides a DSN
    sentry_url = os.environ.get("SENTRY_URL", None)

    # the middleware interferes with interactive debugging
    # to "fix" that, we don't want to integrate Sentry when it's enabled
    if not debug and sentry_url:
        print("Setting up Sentry integration")
        sentry_sdk.init(dsn=sentry_url)

        app = SentryAsgiMiddleware(app)

    return app
