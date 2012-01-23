import zmq
import time

c = zmq.Context()
s = c.socket(zmq.XREP)
s.bind('tcp://127.0.0.1:10001')

while True:
    msg = s.recv_multipart()
    print 'received', msg
    s.send_multipart(msg)
    
