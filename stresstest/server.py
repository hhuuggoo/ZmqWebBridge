from gevent_zeromq import zmq
import gevent
import gevent.monkey
gevent.monkey.patch_all()
from gevent import spawn
import time
import logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

num_reqrep = 20
rr = []
def rr_test(s):
    while True:
        msg = s.recv()
        log.debug(msg)
        s.send(msg)
ctx = zmq.Context()
for c in range(num_reqrep):
    s = ctx.socket(zmq.REP)
    s.setsockopt(zmq.HWM, 100)
    port = s.bind_to_random_port("tcp://127.0.0.1")
    t = spawn(rr_test, s)
    rr.append((s,t, port))

with open("rrports.txt","w+") as f:
    f.write(",".join([str(x[-1]) for x in rr]))

threads = [x[1] for x in rr]
gevent.joinall(threads)





