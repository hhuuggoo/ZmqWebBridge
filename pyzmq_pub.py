import zmq
import time

c = zmq.Context()
s = c.socket(zmq.PUB)
s.bind('tcp://127.0.0.1:10002')
while(True):
    for c  in  range(100):
        print c
        s.send(str(c))
        time.sleep(1)

    
