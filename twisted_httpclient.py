from io import BytesIO
from tornado.concurrent import Future
from tornado.escape import utf8
from tornado import gen
from tornado.httpclient import AsyncHTTPClient, HTTPResponse
from tornado.httputil import HTTPHeaders
from tornado.platform.twisted import TornadoReactor
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

#import signal;signal.alarm(10)

def DeferredFuture(d):
    f = Future()
    d.addCallback(f.set_result)
    d.addErrback(f.set_exception)
    return f

# Copied from http://twistedmatrix.com/documents/current/web/howto/client.html
from zope.interface import implements

from twisted.internet.defer import succeed
from twisted.web.iweb import IBodyProducer

class StringProducer(object):
    implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class Accumulator(Protocol):
    def __init__(self):
        self.done = Future()
        self.buffer = BytesIO()

    def dataReceived(self, chunk):
        self.buffer.write(chunk)

    def connectionLost(self, reason):
        self.done.set_result(self.buffer)


class TwistedHTTPClient(AsyncHTTPClient):
    def initialize(self, io_loop, defaults=None):
        super(TwistedHTTPClient, self).initialize(io_loop, defaults=defaults)
        self.reactor = TornadoReactor(io_loop)
        self.agent = Agent(self.reactor)
        try:
            1/0
        except:
            import sys
            self.reactor.exc_info = sys.exc_info()

    def close(self):
        super(TwistedHTTPClient, self).close()
        self.reactor.fireSystemEvent('shutdown')
        self.reactor = None

    @gen.coroutine
    def fetch_impl(self, request, callback):
        try:
            if request.body is None:
                body_producer = None
            else:
                body_producer = StringProducer(request.body)
            header_dict = dict((k, [v]) for (k, v) in request.headers.items())
            if request.method == "POST" and "Content-Type" not in header_dict:
                header_dict["Content-Type"] = ["application/x-www-form-urlencoded"]
            response = yield DeferredFuture(self.agent.request(
                request.method,
                utf8(request.url),
                Headers(header_dict),
                body_producer))
            accum = Accumulator()
            response.deliverBody(accum)
            body_buffer = yield accum.done
            headers = HTTPHeaders()
            for k, vs in response.headers.getAllRawHeaders():
                for v in vs:
                    headers.add(k, v)
            if ('Content-Length' not in headers and
                response.code not in (204, 304)):
                headers['Content-Length'] = str(len(body_buffer.getvalue()))
            callback(HTTPResponse(
                request, response.code, buffer=body_buffer,
                headers=headers))
        except Exception as e:
            import logging
            logging.warning('error', exc_info=True)
            callback(HTTPResponse(request, code=599, error=e))
