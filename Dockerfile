FROM docker:1.12.2

MAINTAINER Dmitry Drozdov, https://github.com/ddrozdov

RUN apk add --update python py-pip && rm -rf /var/cache/apk/*

RUN pip install docker-compose-swarm-mode

ENTRYPOINT ["docker-compose-swarm-mode"]
