#! /usr/bin/env python3

import functools
import json
import logging
import random
import re
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


class DataJsonHandler(tornado.web.RequestHandler):
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
            yield self.fetch_data_and_assemble_response()

        else:
            self.add_default_headers()
            self.write(self._cached_response)

    def validate_response(self, response: tornado.httpclient.HTTPResponse):
        if response.error:
            # release lock in case of errors
            self.__class__._lock.release()
            self.logger.log(
                logging.ERROR,
                "GitHub API error: {}".format(response.error)
            )
            self.send_error(500)
            return False

        return True

    @gen.coroutine
    def fetch_data_and_assemble_response(self):
        yield self.__class__._lock.acquire()

        self.logger.log(logging.INFO, "Fetching latest release from GitHub")

        releases_url_template = "https://gitlab.com/fdroid/fdroiddata/raw/master/metadata/{}.txt"
        stable_url = releases_url_template.format("org.schabi.newpipe")
        beta_url = releases_url_template.format("org.schabi.newpipe.beta")

        repo_url = "https://api.github.com/repos/TeamNewPipe/NewPipe"

        translations_url = "https://hosted.weblate.org/api/components/" \
                           "newpipe/strings/translations/"

        def make_request(url: str):
            kwargs = dict(headers={
                "User-Agent": ""
            })
            return tornado.httpclient.HTTPRequest(url, **kwargs)

        def fetch(request: tornado.httpclient.HTTPRequest):
            http_client = tornado.httpclient.AsyncHTTPClient()
            return http_client.fetch(request, raise_error=False)

        responses = yield tornado.gen.multi((
            fetch(make_request(repo_url)),
            fetch(make_request(stable_url)),
            fetch(make_request(beta_url)),
            fetch(make_request(repo_url + "/contributors")),
            fetch(make_request(translations_url)),
        ))

        for response in responses:
            if not self.validate_response(response):
                return False

        repo_data, stable_data, beta_data, \
        contributors_data, translations_data = [x.body for x in responses]

        def assemble_release_data(data: str):
            if isinstance(data, bytes):
                data = data.decode()

            versions = re.findall("commit=(.*)", data)

            return {
                "version": versions[-1],
            }

        repo = json.loads(repo_data)
        contributors = json.loads(contributors_data)
        translations = json.loads(translations_data)

        data = {
            "stats": {
                "stargazers": repo["stargazers_count"],
                "watchers": repo["subscribers_count"],
                "forks": repo["forks_count"],
                "contributors": len(contributors),
                "translations": int(translations["count"]),
            },
            "flavors": {
                "stable": assemble_release_data(stable_data),
                "beta": assemble_release_data(beta_data),
            }
        }

        # update cache
        self.update_cache(data)

        # once cache is updated, release lock
        self.__class__._lock.release()

        # finish response
        self.add_default_headers()
        self.write(data)
        self.finish()

    @classmethod
    def update_cache(cls, data):
        cls._cached_response = data
        now = datetime.now()
        cls._last_request = now


def make_app():
    return tornado.web.Application([
        (r"/data.json", DataJsonHandler),
    ])


if __name__ == "__main__":
    tornado.options.parse_command_line()

    app = make_app()
    app.listen(3000)

    tornado.ioloop.IOLoop.current().start()
