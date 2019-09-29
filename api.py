#! /usr/bin/env python3

import json
import logging
import os
import random
import re
import string
import tornado.httpclient
import tornado.ioloop
import tornado.locks
import tornado.options
import tornado.web

from datetime import datetime, timedelta

import yaml
from lxml import html
from tornado import gen

from raven.contrib.tornado import AsyncSentryClient, SentryMixin


def random_string(length=20):
    alphabet = string.ascii_letters + string.digits + "_/-.;:#+*?()$[]!"
    return "".join((random.choice(alphabet) for _ in range(length)))


def fetch(url: str):
    request = tornado.httpclient.HTTPRequest(url, headers={
        "User-Agent": ""
    })
    http_client = tornado.httpclient.AsyncHTTPClient()
    return http_client.fetch(request, raise_error=True)


@gen.coroutine
def get_github_flavor(repo_name: str):
    url = "https://github.com/TeamNewPipe/{}/releases/".format(repo_name)
    html_string = (yield fetch(url)).body
    document = html.fromstring(html_string)

    @gen.coroutine
    def get_version_str() -> str:
        tags = document.cssselect(".release .float-left ul li a.css-truncate > span.css-truncate-target")
        return tags[0].text

    gradle_template = "https://raw.githubusercontent.com/TeamNewPipe/{}/{}/app/build.gradle"

    @gen.coroutine
    def get_version_code() -> int:
        tags = document.cssselect(".release .float-left ul li a code")
        repo_hash = tags[0].text

        gradle_file_data = (yield fetch(gradle_template.format(repo_name, repo_hash))).body
        if isinstance(gradle_file_data, bytes):
            gradle_file_data = gradle_file_data.decode()

        version_codes = re.findall("versionCode(.*)", gradle_file_data)
        return int(version_codes[0].split(" ")[-1])

    @gen.coroutine
    def get_apk_url() -> str:
        tags = document.cssselect('.release-main-section details a[href$=".apk"]')
        return "https://github.com" + tags[0].get("href")

    return {
        "stable": (yield gen.multi({
            "version": get_version_str(),
            "version_code": get_version_code(),
            "apk": get_apk_url(),
        }))
    }


@gen.coroutine
def get_fdroid_flavor(package_name: str):
    template = "https://gitlab.com/fdroid/fdroiddata/raw/master/metadata/{}.yml"
    url = template.format(package_name)

    version_data = (yield fetch(url)).body
    if isinstance(version_data, bytes):
        version_data = version_data.decode()

    data = yaml.safe_load(version_data)

    latest_version = data["Builds"][-1]
    version = latest_version["versionName"]
    version_code = latest_version["versionCode"]

    apk_template = "https://f-droid.org/repo/{}_{}.apk"
    apk_url = apk_template.format(package_name, version_code)

    return {
        "stable": {
            "version": version,
            "version_code": version_code,
            "apk": apk_url,
        }
    }


@gen.coroutine
def assemble_stats():
    repo_url = "https://api.github.com/repos/TeamNewPipe/NewPipe"
    contributors_url = "https://github.com/TeamNewPipe/NewPipe"
    translations_url = "https://hosted.weblate.org/api/components/newpipe/" \
                       "strings/translations/"
    repo_data, contributors_data, translations_data = \
        [x.body for x in (yield gen.multi((
            fetch(repo_url),
            fetch(contributors_url),
            fetch(translations_url),
        )))]

    repo = json.loads(repo_data.decode())

    translations = json.loads(translations_data.decode())

    document = html.fromstring(contributors_data)
    tags = document.cssselect(".numbers-summary a[href$=contributors] .num")
    contributors = int(tags[0].text)

    return {
        "stargazers": repo["stargazers_count"],
        "watchers": repo["subscribers_count"],
        "forks": repo["forks_count"],
        "contributors": contributors,
        "translations": int(translations["count"]),
    }


def assemble_flavors():
    return gen.multi({
        "github": get_github_flavor("NewPipe"),
        "fdroid": get_fdroid_flavor("org.schabi.newpipe"),
        "github_legacy": get_github_flavor("NewPipe-legacy"),
        "fdroid_legacy": get_fdroid_flavor("org.schabi.newpipelegacy"),
    })


class DataJsonHandler(tornado.web.RequestHandler, SentryMixin):
    # 1 hour as a timeout is neither too outdated nor requires bothering GitHub
    # too often
    _timeout = timedelta(hours=1)
    _error_timeout = timedelta(minutes=6)

    # initialize with datetime that is outdated for sure
    _last_request = (datetime.now() - 2 * _timeout)

    # cache for last returned data
    _cached_response = None

    # request GitHub only once when multiple requests are made in parallel
    _lock = tornado.locks.Lock()

    # make sure to not send too many requests to the GitHub API to not trigger
    # the rate limit
    _last_failed_request = (datetime.now() - 2 * _timeout)

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
        # ensure that timeout is respected
        now = datetime.now()

        if self.__class__._last_failed_request is not None and \
                (now - self.__class__._last_failed_request) < self.__class__._error_timeout:
            self.logger.log(logging.INFO,
                            "Request failed recently, waiting for timeout")
            self.add_default_headers()
            self.send_error(500)
            return

        yield self.__class__._lock.acquire()

        if self.is_request_outdated():
            yield self.assemble_fresh_response()

        else:
            self.add_default_headers()
            self.write(self._cached_response)

        yield self.__class__._lock.release()

    @gen.coroutine
    def assemble_fresh_response(self):
        self.logger.log(logging.INFO, "Fetching latest release from GitHub")

        data = None

        # prove me wrong!
        failure = True

        try:
            data = yield gen.multi({
                "stats": assemble_stats(),
                "flavors": assemble_flavors()
            })

        except tornado.httpclient.HTTPError as error:
            yield gen.Task(self.captureException, "API error")
            response = error.response
            self.logger.log(
                logging.ERROR,
                "API error: {} -> {} ({})".format(response.effective_url, response.error, response.body),
            )

        except:
            self.logger.exception("Unknown error occured, see next line")
            yield gen.Task(self.captureException, exc_info=True)

        else:
            failure = False

        if failure:
            self.__class__._last_failed_request = datetime.now()
            self.send_error(500)
            return False

        self.update_cache(data)
        self.add_default_headers()
        self.write(data)
        self.finish()

    @classmethod
    def update_cache(cls, data):
        cls._cached_response = data
        now = datetime.now()
        cls._last_request = now


def make_app():
    app = tornado.web.Application([
        (r"/data.json", DataJsonHandler),
    ])

    sentry_url = os.environ.get("SENTRY_URL", None)

    if sentry_url is not None:
        print("Setting up Sentry integration")
        app.sentry_client = AsyncSentryClient(sentry_url)

    return app


if __name__ == "__main__":
    tornado.options.parse_command_line()

    app = make_app()
    app.listen(3000)

    tornado.ioloop.IOLoop.current().start()
