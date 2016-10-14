#!/bin/sh

version=`egrep "^version" setup.py | awk -F"'" '{print $2}'`

docker build -t ddrozdov/docker-compose-swarm-mode:$version . &&
  docker tag ddrozdov/docker-compose-swarm-mode:$version ddrozdov/docker-compose-swarm-mode:latest &&
  docker push ddrozdov/docker-compose-swarm-mode:$version &&
  docker push ddrozdov/docker-compose-swarm-mode:latest
