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

        @contextlib.contextmanager
        def cleanup():
            try:
                yield
            except Exception, e:
                logging.warning("uncaught exception", exc_info=True)
                callback(HTTPResponse(request, 599, error=e))
        with stack_context.StackContext(cleanup):
            parsed = urlparse.urlsplit(request.url)
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
                stream = SSLIOStream(sock, io_loop=self.io_loop)
            else:
                stream = IOStream(sock, io_loop=self.io_loop)
            if "Host" not in request.headers:
                request.headers["Host"] = parsed.netloc
            has_body = request.method in ("POST", "PUT")
            if has_body:
                assert request.body is not None
                request.headers["Content-Length"] = len(request.body)
            else:
                assert request.body is None
            req_path = ((parsed.path or '/') +
                    (('?' + parsed.query) if parsed.query else ''))
            request_lines = ["%s %s HTTP/1.1" % (request.method, req_path)]
            for k, v in request.headers.get_all():
                request_lines.append("%s: %s" % (k, v))
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                for line in request_lines:
                    logging.debug(line)
            stream.write("\r\n".join(request_lines) + "\r\n\r\n")
            if has_body:
                stream.write(request.body)
            stream.read_until("\r\n\r\n", functools.partial(self._on_headers,
                                                            request, callback, stream))

    def _on_headers(self, request, callback, stream, data):
        logging.debug(data)
        first_line, _, header_data = data.partition("\r\n")
        match = re.match("HTTP/1.[01] ([0-9]+) .*", first_line)
        assert match
        code = int(match.group(1))
        headers = HTTPHeaders.parse(header_data)
        if request.header_callback is not None:
            for k, v in headers.get_all():
                request.header_callback("%s: %s\r\n" % (k, v))
        if headers.get("Transfer-Encoding") == "chunked":
            chunks = []
            stream.read_until("\r\n", functools.partial(self._on_chunk_length,
                                                        request, callback, stream, code, headers, chunks))
        elif "Content-Length" in headers:
            stream.read_bytes(int(headers["Content-Length"]),
                              functools.partial(self._on_body, request, callback, stream, code, headers))
        else:
            raise Exception("No Content-length or chunked encoding, "
                            "don't know how to read")

    def _on_body(self, request, callback, stream, code, headers, data):
        response = HTTPResponse(request, code, headers=headers,
                                buffer=StringIO(data)) # TODO
        callback(response)

    def _on_chunk_length(self, request, callback, stream, code, headers, chunks, data):
        # TODO: "chunk extensions" http://tools.ietf.org/html/rfc2616#section-3.6.1
        length = int(data.strip(), 16)
        if length == 0:
            self._on_body(request, callback, stream, code, headers,
                          ''.join(chunks))
        else:
            stream.read_bytes(length + 2,  # chunk ends with \r\n
                              functools.partial(self._on_chunk_data,
                                                request, callback, stream,
                                                code, headers, chunks))

    def _on_chunk_data(self, request, callback, stream, code, headers, chunks, data):
        assert data[-2:] == "\r\n"
        chunk = data[:-2]
        if request.streaming_callback is not None:
            request.streaming_callback(chunk)
        else:
            chunks.append(chunk)
        stream.read_until("\r\n", functools.partial(self._on_chunk_length,
                                                    request, callback, stream, code, headers, chunks))


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
