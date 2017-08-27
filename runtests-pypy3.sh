#!/bin/sh

docker run -v "$PWD":/tornado pypy:3 env PYTHONPATH=/tornado pypy3 -m tornado.test "$@"
