#!/usr/bin/env python
from __future__ import with_statement

from cStringIO import StringIO
from tornado.httpclient import HTTPRequest, HTTPResponse, HTTPError
from tornado.httputil import HTTPHeaders
from tornado.ioloop import IOLoop
from tornado.iostream import IOStream, SSLIOStream
from tornado import stack_context

import contextlib
import functools
import logging
import re
import socket
import urlparse

try:
    import ssl # python 2.6+
except ImportError:
    ssl = None

class SimpleAsyncHTTPClient(object):
    # TODO: singleton magic?
    def __init__(self, io_loop=None):
        self.io_loop = io_loop or IOLoop.instance()

    def close(self):
        pass

    def fetch(self, request, callback, **kwargs):
        if not isinstance(request, HTTPRequest):
            request = HTTPRequest(url=request, **kwargs)
        if not isinstance(request.headers, HTTPHeaders):
            request.headers = HTTPHeaders(request.headers)
        callback = stack_context.wrap(callback)
        _HTTPConnection(self.io_loop, request, callback)



class _HTTPConnection(object):
    def __init__(self, io_loop, request, callback):
        self.io_loop = io_loop
        self.request = request
        self.callback = callback
        self.code = None
        self.headers = None
        self.chunks = None
        with stack_context.StackContext(self.cleanup):
            parsed = urlparse.urlsplit(self.request.url)
            sock = socket.socket()
            #sock.setblocking(False) # TODO non-blocking connect
            if ":" in parsed.netloc:
                host, _, port = parsed.netloc.partition(":")
                port = int(port)
            else:
                host = parsed.netloc
                port = 443 if parsed.scheme == "https" else 80
            sock.connect((host, port))
            if parsed.scheme == "https":
                # TODO: cert verification, etc
                sock = ssl.wrap_socket(sock, do_handshake_on_connect=False)
                self.stream = SSLIOStream(sock, io_loop=self.io_loop)
            else:
                self.stream = IOStream(sock, io_loop=self.io_loop)
            if "Host" not in self.request.headers:
                self.request.headers["Host"] = parsed.netloc
            has_body = self.request.method in ("POST", "PUT")
            if has_body:
                assert self.request.body is not None
                self.request.headers["Content-Length"] = len(
                    self.request.body)
            else:
                assert self.request.body is None
            if (self.request.method == "POST" and
                "Content-Type" not in self.request.headers):
                self.request.headers["Content-Type"] = "application/x-www-form-urlencoded"
            req_path = ((parsed.path or '/') +
                    (('?' + parsed.query) if parsed.query else ''))
            request_lines = ["%s %s HTTP/1.1" % (self.request.method,
                                                 req_path)]
            for k, v in self.request.headers.get_all():
                request_lines.append("%s: %s" % (k, v))
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                for line in request_lines:
                    logging.debug(line)
            self.stream.write("\r\n".join(request_lines) + "\r\n\r\n")
            if has_body:
                self.stream.write(self.request.body)
            self.stream.read_until("\r\n\r\n", self._on_headers)

    @contextlib.contextmanager
    def cleanup(self):
        try:
            yield
        except Exception, e:
            logging.warning("uncaught exception", exc_info=True)
            if self.callback is not None:
                self.callback(HTTPResponse(self.request, 599, error=e))
                self.callback = None

    def _on_headers(self, data):
        logging.debug(data)
        first_line, _, header_data = data.partition("\r\n")
        match = re.match("HTTP/1.[01] ([0-9]+) .*", first_line)
        assert match
        self.code = int(match.group(1))
        self.headers = HTTPHeaders.parse(header_data)
        if self.request.header_callback is not None:
            for k, v in self.headers.get_all():
                self.request.header_callback("%s: %s\r\n" % (k, v))
        if self.headers.get("Transfer-Encoding") == "chunked":
            self.chunks = []
            self.stream.read_until("\r\n", self._on_chunk_length)
        elif "Content-Length" in self.headers:
            self.stream.read_bytes(int(self.headers["Content-Length"]),
                                   self._on_body)
        else:
            raise Exception("No Content-length or chunked encoding, "
                            "don't know how to read %s", self.request.url)

    def _on_body(self, data):
        if self.request.streaming_callback:
            if self.chunks is None:
                # if chunks is not None, we already called streaming_callback
                # in _on_chunk_data
                self.request.streaming_callback(data)
            buffer = StringIO()
        else:
            buffer = StringIO(data) # TODO: don't require one big string?
        response = HTTPResponse(self.request, self.code, headers=self.headers,
                                buffer=buffer)
        self.callback(response)
        self.callback = None

    def _on_chunk_length(self, data):
        # TODO: "chunk extensions" http://tools.ietf.org/html/rfc2616#section-3.6.1
        length = int(data.strip(), 16)
        if length == 0:
            self._on_body(''.join(self.chunks))
        else:
            self.stream.read_bytes(length + 2,  # chunk ends with \r\n
                              self._on_chunk_data)

    def _on_chunk_data(self, data):
        assert data[-2:] == "\r\n"
        chunk = data[:-2]
        if self.request.streaming_callback is not None:
            self.request.streaming_callback(chunk)
        else:
            self.chunks.append(chunk)
        self.stream.read_until("\r\n", self._on_chunk_length)


def main():
    from tornado.options import define, options, parse_command_line
    args = parse_command_line()
    client = SimpleAsyncHTTPClient()
    io_loop = IOLoop.instance()
    for arg in args:
        def callback(response):
            io_loop.stop()
            response.rethrow()
            print response.body
        client.fetch(arg, callback)
        io_loop.start()

if __name__ == "__main__":
    main()
