# Dockerfile: 
#     Adapts the official nginx Alpine image to generate a default self-signed certificate.
#     Injects a python script called before the nginx service is started, to fetch  certificates from S3.
#
# SPDX-License-Identifier: Apache 2.0


FROM nginx:stable-alpine
COPY ./nginx.conf /etc/nginx/nginx.conf


RUN mkdir -p  /etc/nginx/ssl
WORKDIR /etc/nginx/ssl
COPY selfsignedcert.sh .
RUN chmod +x ./selfsignedcert.sh



COPY certConfig.py /etc/nginx/certConfig.py 
COPY requirements.txt /etc/nginx/ssl/requirements.txt

COPY configureCerts.sh /docker-entrypoint.d/ 
RUN chmod +x /docker-entrypoint.d/configureCerts.sh

EXPOSE 443

RUN apk add python3
RUN apk add py3-pip
RUN apk add openssl
RUN apk add --no-cache --upgrade bash

RUN pip install -r requirements.txt

#Create self-signed certificate.
RUN bash ./selfsignedcert.sh certificate