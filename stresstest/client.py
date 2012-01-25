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

with open("rrports.txt","r") as f:
    ports = [int(x) for x in f.read().split(",")]
results = {}
def test(port, sock_type, num_reqs):
    identity = str(uuid.uuid4())
    results[port, identity] = 0
    sock = websocket.WebSocket()
    sock.io_sock.settimeout(1.0)
    zmq_conn_string = "tcp://127.0.0.1:" + str(port)
    sock.connect('ws://127.0.0.1:9000')
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
        try:
            sock.send(simplejson.dumps(
                {'identity' : identity,
                 'msg_type' : 'user',
                 'content' : identity}))
            msg = sock.recv()
            log.debug(msg)
            assert simplejson.loads(msg)['content'] == identity
            #print identity
            results[port, identity] += 1
        except:
            pass
    sock.close()

num_reqs = 100
num_per_port = 10
num_ports = len(ports)
while True:
    threads = []
    for p in ports:
        for c in range(num_per_port):
            threads.append(spawn(test, p, zmq.REQ, num_reqs))
    #threads = [spawn(test, p, zmq.REQ, 100) for p in ports]
    def report():
        while(True):
            log.info("%s, %s, %s", len(results),
                      np.sum(np.array(results.values())),
                      num_reqs * num_per_port * num_ports)
            gevent.sleep(1)
    threads.append(spawn(report))
    gevent.sleep(5.0)
    [x.kill() for x in threads]
