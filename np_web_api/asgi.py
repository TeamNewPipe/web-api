from . import make_app
from ._logging import configure_logging


def make_production_app():
    """
    Configure logging before creating the application. Useful with application servers, where it's pretty impossible to
    run code other than the app factory.
    :return: standard app created by make_app
    """

    configure_logging()

    return make_app()


app = make_production_app()
