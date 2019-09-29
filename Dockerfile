FROM python:3.6-alpine

MAINTAINER "TheAssassin <theassassin@assassinate-you.net>"

# install dependencies
RUN apk add --no-cache gcc libxml2-dev libxml2 musl-dev xmlsec xmlsec-dev curl

# create non-root user
RUN adduser -S app

COPY requirements.txt /
RUN pip install -r requirements.txt

USER app

HEALTHCHECK --interval=5m --timeout=3s \
    CMD curl -f http://localhost:3000/data.json || exit 1

EXPOSE 3000

ENTRYPOINT ["python", "api.py"]

COPY api.py /
