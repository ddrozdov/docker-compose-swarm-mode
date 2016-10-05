# Docker Compose for Swarm Mode

Drop in replacement for docker-compose that works with swarm mode introduced in Docker 1.12.  

## Motivation

Docker 1.12 with its new [Swarm mode](https://docs.docker.com/engine/swarm/) has been out for a while, but Docker Compose - the great tool for running multi-container configurations - still (1.5+ months after Docker release) doesn't support it.

The only thing they offer is generating a [DAB](https://github.com/docker/docker/blob/master/experimental/docker-stacks-and-bundles.md) file from your `docker-compose.yml` and deploying it to Docker.
However DAB doesn't support a lot of `docker-compose.yml` stuff and deploying it to Docker is an experimental feature that is not supported yet in the latest 1.12.1 release.

So you should either stick with the previous version of Docker or throw out all your docker-compose files and run a bunch of long `docker service ...` commands.

Neither option looked good to me so, as a temporary solution (I still hope Docker Compose with swarm mode support will be released soon), I've created a script that parses a `docker-compose.yml` file, generates `docker service ...` commands for you and runs them.

## Installation

docker-compose-swarm-mode is available on [PyPI](https://pypi.python.org/pypi/docker-compose-swarm-mode).

`pip install docker-compose-swarm-mode`

Or just download the `.py` script.

## Requirements

Python 2.7+.

## Usage

The script tries its best to support the CLI of the original Docker Compose so just use it as you would use Docker Compose.

Use `--dry-run` option if you'd first like to check what `docker` commands are to be executed. 

The script currently doesn't support all docker-compose commands, options, and `yml` keys. It just supports what I've needed in my projects so far.
See the usage help with `-h` flag and try the script with your `docker-compose.yml`, it'll tell you if there are unsupported keys.

In case you need something that is not supported yet, feel free to create an issue and/or submit a pull request.

Keys that are silently ignored because they are not supported by `docker service`:
* container_name
* expose
* extra_hosts
* hostname

## History

#### 1.2.0

Fix services, networks, and volumes being incorrectly detected as existing/running in some cases.

Fix spaces handling in variables under `environment` key.

Support for multiple compose files.

Support for `.env` file.

#### 1.1.1

Fix pypandoc being required on installation while needed on packaging phase only.

#### 1.1.0

Python 3 support.

Installation from PyPI.

#### 1.0.0

First release.

## License

The MIT License (MIT)

Copyright (c) 2016 Dmitry Drozdov

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
