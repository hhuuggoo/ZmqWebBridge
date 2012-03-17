import gevent.monkey
gevent.monkey.patch_all()
from gevent_zeromq import zmq
import gevent
import time

c = zmq.Context()
s = c.socket(zmq.XREP)
s.bind('tcp://127.0.0.1:10001')
ident = None
def loop():
    global ident
    while True:
        print 'starting'
        msg = s.recv_multipart()
        print 'received', msg
        if 'IDENT' in msg[-1]:
            ident = msg[-1].split()[-1]
        s.send_multipart(msg)
reploop = gevent.spawn(loop)
s2 = c.socket(zmq.REQ)
s2.connect('tcp://127.0.0.1:10003')
while(True):
    for c  in  range(100):
        if ident is not None:
            print 'sending %s' % c
            s2.send_multipart([str(c), ident]);
            print s2.recv();
        gevent.sleep(1)

    



