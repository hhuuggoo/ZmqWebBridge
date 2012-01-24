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
import uuid

import test_utils


with open("rrports.txt","r") as f:
    ports = [int(x) for x in f.read().split(",")]
results = {}
def test(port, sock_type, num_reqs):
    identity = str(uuid.uuid4())
    results[port, identity] = 0
    sock = websocket.WebSocket()
    sock.io_sock.settimeout(1.0)
    zmq_conn_string = "tcp://127.0.0.1:" + str(port)
    sock.connect('ws://127.0.0.1:8000')
    auth = {
        'zmq_conn_string' : zmq_conn_string,
        'socket_type' : sock_type
        }
    auth = simplejson.dumps(auth)
    sock.send(simplejson.dumps(
        {
            'identity' : identity,
            'msg_type' : 'connect',
            'content' : auth
        }))
    msg = sock.recv()
    for c in range(num_reqs):
        sock.send(simplejson.dumps(
            {'identity' : identity,
             'msg_type' : 'user',
             'content' : identity}))
        assert simplejson.loads(sock.recv())['content'] == identity
        #print identity
        results[port, identity] += 1
    sock.close()

num_reqs = 100
num_per_port = 30
num_ports = len(ports)
threads = []
for p in ports:
    for c in range(num_per_port):
        threads.append(spawn(test, p, zmq.REQ, num_reqs))
#threads = [spawn(test, p, zmq.REQ, 100) for p in ports]
gevent.joinall(threads)
print len(results)
print np.sum(np.array(results.values()))
print  num_reqs * num_per_port * num_ports



