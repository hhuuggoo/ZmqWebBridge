import numpy as np
import websocket
from gevent_zeromq import zmq
import gevent
import gevent.monkey
gevent.monkey.patch_all()
from gevent import spawn
from geventwebsocket.handler import WebSocketHandler
import bridge
from gevent import pywsgi
import time
import logging
log = logging.getLogger(__name__)
import simplejson
logging.basicConfig(level=logging.INFO)

import bsddb
app = bridge.WsgiHandler()
server = pywsgi.WSGIServer(('0.0.0.0', 8000), app.wsgi_handle,
                           handler_class=WebSocketHandler)
bridge_thread = spawn(server.serve_forever)

num_reqrep = 20
rr = []
def rr_test(s):
    while True:
        msg = s.recv()
        s.send(msg)

for c in range(num_reqrep):
    ctx = zmq.Context()
    s = ctx.socket(zmq.REP)
    port = s.bind_to_random_port("tcp://127.0.0.1")
    t = spawn(rr_test, s)
    rr.append((s,t, port))

with open("rrports.txt","w+") as f:
    f.write(",".join([str(x[-1]) for x in rr]))

bridge_thread.join()




