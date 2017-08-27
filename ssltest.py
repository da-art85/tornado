import socket, ssl, os

sock = socket.socket()
sock.connect(('www.google.com', 443))

ssl_sock = ssl.wrap_socket(sock)
os.close(ssl_sock.fileno())
print(ssl_sock.read())
