# NewPipe Website API

This project provides the NewPipe website with data feeds of externally
stored data. Such data is for example the current version of the app, which
can be fetched via the GitHub API.

While web APIs like the GitHub one could be requested directly from the
browser, this has a couple of disadvantages. The most relevant is probably
that issuing requests from our website to GitHub compromises our idea of
improved privacy by hosting websites without any trackers on our own
infrastructure. By requesting the GitHub API from the users' browsers, the
browser will most likely send headers in those requests containing information
on the origin of the requests (so-called `Referer:` header). The only way to
avoid this is to provide the data from the same infrastructure as the main
website, and that's the idea behind this project.

The project is written in Python 3 and uses the
[Tornado framework](http://www.tornadoweb.org) to build a blazing fast, yet
efficient web API following the micro service design pattern. The API fetches
the upstream data, e.g., from GitHub, extracts the relevant bits, and returns
them either as raw string or serialized as JSON.

Furthermore, it is capable of caching the latest data, to on the one hand
reduce the amount of requests (and outgoing traffic) to the upstream APIs, and
on the other hand reduce the response time to a minimum, especially for
subsequent requests. This works really well due to the asynchronous model
Tornado provides.
