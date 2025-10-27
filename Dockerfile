FROM python:3.10-slim-bookworm
ARG ENVIRONMENT

WORKDIR /usr/src/app

# upgrade to latest pip
RUN pip install --upgrade pip
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y git

# Install workflows-cdk package
RUN pip install git+https://github.com/stacksyncdata/workflows-cdk.git@prod

# install dependencies
COPY requirements.txt ./
RUN pip3 install -r requirements.txt

# copy the scripts
COPY / .

# setup flask server
# expose port
EXPOSE 8080
#set environment variable on linux: export PORT=2001
CMD exec gunicorn --bind 8080:8080

# make the entrypoint executable
RUN chmod +x ./entrypoint.sh

# run the entrypoint to start the Guicorn production server
ENTRYPOINT ["sh", "entrypoint.sh"]


# RUN in interactive mode
# UNIX: docker run --rm -p 2001:8080 -it -e ENVIRONMENT=dev -e REGION=besg -v $PWD:/usr/src/app/ workflows-app-example
# Windows: docker run --rm -p 2001:8080 -it -e ENVIRONMENT=dev -e REGION=besg -v ${PWD}:/usr/src/app/ workflows-app-example

# BUILD container
# docker build -t workflows-app-example . --build-arg ENVIRONMENT=dev
# docker build --no-cache -t workflows-app-example . --build-arg ENVIRONMENT=dev

# CONNECT to container terminal
# docker exec -it workflows-app-example bash
