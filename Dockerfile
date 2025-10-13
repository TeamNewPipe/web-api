FROM python:3.14.0-slim

LABEL org.opencontainers.image.source="https://github.com/TeamNewPipe/web-api"

MAINTAINER "TheAssassin <theassassin@assassinate-you.net>"

# this port won't ever change, really
EXPOSE 5000

# create non-root user
RUN adduser app

USER app
WORKDIR /app

COPY README.md pyproject.toml poetry.lock /app/
COPY np_web_api/ /app/np_web_api/

# note: pip doesn't support editable (-e) installs with pyproject.toml only
RUN pip install .

HEALTHCHECK --interval=5m --timeout=15s \
    CMD curl -f http://localhost:5000/data.json || exit 1

# using just one worker worked fine so far, and allows for some very crappy "synchronization" between requests by just
# using global variables, which help prevent concurrent requests to update cached data
CMD ["python", "-m", "uvicorn", "np_web_api.asgi:app", "--host", "0.0.0.0", "--port", "5000", "--workers", "1", "--no-access-log"]
