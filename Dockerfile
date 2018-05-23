FROM python:3.6-alpine

MAINTAINER "TheAssassin <theassassin@assassinate-you.net>"

# install dependencies
RUN apk add --no-cache gcc libxml2-dev libxml2 musl-dev xmlsec xmlsec-dev

# create non-root user
RUN adduser -S app

COPY requirements.txt /
RUN pip install -r requirements.txt

USER app

COPY api.py /

EXPOSE 3000

ENTRYPOINT ["python", "api.py"]
