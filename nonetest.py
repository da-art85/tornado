from tornado.httpclient import HTTPClient, HTTPRequest, AsyncHTTPClient

AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient')

HTTPClient().fetch(HTTPRequest('http://www.google.com', headers={'foo': None}))
