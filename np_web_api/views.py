import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
import sentry_sdk
from lxml import html
from quart import Response, jsonify

from . import bp, cache
from ._logging import make_logger
from ._util import fetch_text, RateLimitExceededError


logger = make_logger("views")


async def get_info_from_fdroid_repo(package: str, repo_url: str):
    """
    Get the APK info from an F-Droid repository.
    :param package: the package name
    :param repo_url: the repository URL with a trailing slash '/'
    :return: dict with the parsed info
    """
    # TODO in case multiple packages are read from one repo: pre-fetch indices before calling this coroutine
    json_string = await fetch_text(repo_url + "index-v1.json")
    data = json.loads(json_string)

    version = -1
    version_code = -1
    apk_url = -1
    hash_sum = -1,
    hash_type = -1

    if 'apps' in data:
        for app in data['apps']:
            if app['packageName'] == package:
                version = app['suggestedVersionName']
                # why the hell is the code a string here apps, but an int below in packages...
                version_code = int(app['suggestedVersionCode'])
                break

        if 'packages' in data and package in data['packages']:
            for version_info in data['packages'][package]:
                logger.info(version_code)
                logger.info(version_info['versionCode'])
                logger.info(version_info)
                if version_info['versionCode'] == version_code:
                    version = version_info['versionName']
                    version_code = version_info['versionCode']

                    apk_name = version_info['apkName']
                    apk_url = repo_url + apk_name

                    hash_sum = version_info['hash']
                    hash_type = version_info['hashType']

    return {
        "version": version,
        "version_code": version_code,
        "apk": apk_url,
        "hash": hash_sum,
        "hash_type": hash_type
    }


async def assemble_flavors():
    newpipe_flavor, fdroid_flavor = await asyncio.gather(
        get_info_from_fdroid_repo("org.schabi.newpipe", "https://archive.newpipe.net/fdroid/repo/"),
        get_info_from_fdroid_repo("org.schabi.newpipe", "https://f-droid.org/repo/"),
    )

    return {
        "newpipe": newpipe_flavor,
        "fdroid": fdroid_flavor,
    }


async def assemble_stats():
    repo_url = "https://api.github.com/repos/TeamNewPipe/NewPipe"
    contributors_url = "https://github.com/TeamNewPipe/NewPipe"
    translations_url = "https://hosted.weblate.org/api/components/newpipe/strings/translations/"

    repo_data, contributors_data, translations_data = await asyncio.gather(
        fetch_text(repo_url),
        fetch_text(contributors_url),
        fetch_text(translations_url),
    )

    repo = json.loads(repo_data)
    translations = json.loads(translations_data)

    # no idea why, but sometimes we receive different responses from GitHub
    # might be some annoying A/B testing
    # therefore we make this more fault-tolerant by sending a negative value if we can't fetch the data from GitHub
    document = html.fromstring(contributors_data)
    sidebar_cells_links = document.cssselect(".BorderGrid-cell .h4.mb-3 a")

    try:
        for a in sidebar_cells_links:
            if "contributors" in a.text.lower():
                counter = a.cssselect(".Counter")[0]
                contributors = int(counter.text)
                break

        else:
            raise KeyError("could not find counter value")

    except:  # noqa: E722
        # whatever happens, we will just continue with -1 as default value
        # but we can at least log the exception to sentry
        sentry_sdk.capture_exception()

        # log entire response body to file to allow for inspection
        # with open("/tmp/failed-contributors-response.{}.txt".format(datetime.now().isoformat()), "wb") as f:
        #     f.write(contributors_data)

        contributors = -1

    return {
        "stargazers": repo["stargazers_count"],
        "watchers": repo["subscribers_count"],
        "forks": repo["forks_count"],
        "contributors": contributors,
        "translations": int(translations["count"]),
    }


async def assemble_fresh_response_data() -> dict:
    logger.log(logging.INFO, "Fetching latest release data from third-party APIs")

    # note for self: if it's possible to get a dict out of gather like it was with tornado, this would be great
    stats, flavors = await asyncio.gather(assemble_stats(), assemble_flavors())

    data = {"stats": stats, "flavors": flavors}

    return data


# yeah, yeah, I know, using a module-level variable with a lock isn't that great
# there's a reason we just run this with one worker at a time at the moment... which is more than sufficient, actually
LOCK = asyncio.Lock()


@bp.route("/data.json")
async def data_json():
    # we make the assumption that the cache works perfectly here, i.e., it will always deliver proper data once the
    # values were initially stored into it
    # in reality, it might fail occurrently and return None on all values, but the chance is so low we can ignore that
    last_updated: Optional[datetime]
    data: Optional[dict]
    was_error: Optional[bool]
    last_updated, data, was_error = cache.get_many("last_updated", "data", "was_error")

    def is_outdated(last_updated, data, was_error):
        # check whether we have to update the data
        # we should only do this if:
        #   - this is the first run (first case)
        #   - there was an error and the error timeout is over (second case)
        #   - the last run succeeded, but the timeout is over

        if not last_updated and not data:
            logger.info("first run")
            return True

        if was_error and (last_updated + error_timeout) < now:
            logger.info("error timeout hit")
            return True

        if (last_updated + normal_timeout) < now:
            logger.info("normal timeout hit")
            return True

        logger.debug("request not outdated")
        return False

    # usual timeouts for cached data
    # we do this to avoid sending too many requests to the third-party APIs, as these are usually heavily rate-limited
    error_timeout = timedelta(minutes=6)
    normal_timeout = timedelta(hours=1)

    # we need this value a few times below
    now = datetime.now()

    # if the if doesn't do anything, well, this lock'll return quickly
    # if
    if is_outdated(last_updated, data, was_error):
        # data seems to be outdated,
        async with LOCK:
            # re-check if it's still outdated
            last_updated, data, was_error = cache.get_many("last_updated", "data", "was_error")

            # I know this is kinda ugly, but some other client request may already have filled the cache again
            if not is_outdated(last_updated, data, was_error):
                logger.info("cache was outdated but is now up-to-date thanks to another coroutine")

            else:
                logger.info("cache outdated, assembling fresh response")

                try:
                    # overwrite old data _only_ if there was no error
                    new_data = await assemble_fresh_response_data()

                except aiohttp.client.ClientError:
                    logger.exception("API call failed")
                    was_error = True
                    sentry_sdk.capture_exception()

                except RateLimitExceededError as e:
                    logger.error(str(e))
                    was_error = True
                    sentry_sdk.capture_exception()

                except:  # noqa: E722
                    logger.exception("Unknown error occured, see next line")
                    was_error = True
                    sentry_sdk.capture_exception()

                else:
                    was_error = False
                    data = new_data

                last_updated = now

                # update cache only here to save time
                logger.info("updating cache")
                cache.set_many(
                    {
                        "was_error": was_error,
                        "last_updated": last_updated,
                        "data": data,
                    }
                )

    else:
        logger.debug("cache appears up to date, responding with cached data (if available)")

    # may only ever happen when calls fail directly after a restart
    if was_error:
        if not data:
            logger.debug("error and no cached data, responding with status 500")

            headers = {
                "retry-after": error_timeout.total_seconds(),
            }

            return Response("temporary issues, try again later", 503, headers=headers)

        logger.error("error occurred during data update, responding with old data")

    logger.debug(f"responding cached data: {repr(data)}")

    response = jsonify(data)

    # set CORS header to allow access from any host to the data API
    response.headers.set("Access-Control-Allow-Origin", "*")

    return response
