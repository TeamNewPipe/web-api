#! /usr/bin/env python3

import functools
import json
import logging
import random
import string
import tornado.httpclient
import tornado.ioloop
import tornado.locks
import tornado.options
import tornado.web

from datetime import datetime, timedelta
from tornado import gen


def random_string(length=20):
    alphabet = string.ascii_letters + string.digits + "_/-.;:#+*?()$[]!"
    return "".join((random.choice(alphabet) for i in range(length)))


class CurrentVersionHandler(tornado.web.RequestHandler):
    # 1 hour as a timeout is neither too outdated nor requires bothering
    # GitHub too often
    _timeout = timedelta(hours=1)

    # initialize with datetime that is outdated for sure
    _last_request = (datetime.now() - 2 * _timeout)

    # cache for last returned data
    _cached_response = None

    # request GitHub only once when multiple requests are made in parallel
    _lock = tornado.locks.Lock()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.http_client = tornado.httpclient.AsyncHTTPClient()
        self.logger = logging.getLogger("tornado.general")

    def add_default_headers(self):
        self.add_header("Content-Type", "text/plain")
        self.add_header("Access-Control-Allow-Origin", "newpipe.schabi.org")

    @classmethod
    def is_request_outdated(cls):
        now = datetime.now()

        if cls._cached_response is None:
            return True

        if (now - cls._last_request) > cls._timeout:
            return True

        return False

    @gen.coroutine
    def get(self):
        if self.is_request_outdated():
            yield self.make_request()

        else:
            self.add_default_headers()
            self.write(self._cached_response)

    @gen.coroutine
    def make_request(self):
        yield self.__class__._lock.acquire()

        self.logger.log(logging.INFO, "Fetching latest release from GitHub")

        url = "https://api.github.com/repos/" \
              "TeamNewPipe/NewPipe/releases/latest"

        request = tornado.httpclient.HTTPRequest(url, headers={
            "User-Agent": ""
        })

        yield self.http_client.fetch(request, self.http_callback, False)

    @classmethod
    def update_cache(cls, data):
        cls._cached_response = data
        now = datetime.now()
        cls._last_request = now

    def http_callback(self, response: tornado.httpclient.HTTPResponse):
        if response.error:
            # release lock in case of errors
            self.__class__._lock.release()
            self.logger.log(logging.ERROR,
                            "GitHub API error: {}".format(response.error))
            self.send_error(500)

        else:
            data = json.loads(response.body)

            version = data["name"]

            # update cache
            self.update_cache(version)

            # once cache is updated, release lock
            self.__class__._lock.release()

            # finish response
            self.add_default_headers()
            self.write(version)
            self.finish()


def make_app():
    return tornado.web.Application([
        (r"/current-version", CurrentVersionHandler),
    ])


if __name__ == "__main__":
    tornado.options.parse_command_line()

    app = make_app()
    app.listen(3000)

    tornado.ioloop.IOLoop.current().start()
