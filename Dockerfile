FROM python:3-alpine

MAINTAINER "TheAssassin <theassassin@assassinate-you.net>"

# this port won't ever change, really
EXPOSE 5000

# install dependencies
RUN apk add --no-cache gcc libxml2-dev libxml2 musl-dev xmlsec xmlsec-dev curl libffi-dev openssl-dev make

# create non-root user
RUN adduser -S app

# install poetry system-wide, the rest per user
# for some reason, we can't just pip install the entire package, but have to invoke poetry directly...
RUN pip install poetry

USER app
WORKDIR /app

# must provide both the
COPY pyproject.toml poetry.lock /app/

# note: pip doesn't support editable (-e) installs with pyproject.toml only
RUN poetry install

HEALTHCHECK --interval=5m --timeout=15s \
    CMD curl -f http://localhost:5000/data.json || exit 1

COPY np_web_api/ /app/np_web_api/

# using just one worker worked fine so far, and allows for some very crappy "synchronization" between requests by just
# using global variables, which help prevent concurrent requests to update cached data
CMD ["poetry", "run", "uvicorn", "--factory", "np_web_api:make_production_app", "--host", "0.0.0.0", "--port", "5000", "--workers", "1", "--no-access-log"]
