# Dockerfile: 
#     Adapts the official python 3.8 slim image to run the stowrs-to-s3 service business logic.
#
# SPDX-License-Identifier: Apache 2.

FROM python:3.8-slim-buster
WORKDIR /stowrs-to-s3
RUN mkdir -p /multipart_reader
COPY *.py .
COPY ./multipart_reader/* ./multipart_reader/
COPY requirements.txt .
RUN apt update && apt upgrade
RUN pip install -r requirements.txt 
EXPOSE 8080/tcp
ENTRYPOINT [ "python3" , "main.py" ]