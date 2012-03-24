import zmq
import time

c = zmq.Context()
s = c.socket(zmq.REQ)
s.connect('tcp://127.0.0.1:10003')
while(True):
    for c  in  range(100):
        print 'sending %s' % c
        s.send(str(c))
        print s.recv();
        time.sleep(1)

    
