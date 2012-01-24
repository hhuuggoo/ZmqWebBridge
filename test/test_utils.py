import unittest
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

def wait_until(func, timeout=1.0, interval=0.01):
    st = time.time()
    while True:
        if func():
            return True
        if (time.time() - st) > interval:
            return False
        gevent.sleep(interval)

def connect(server, ws_address, zmq_conn_string, sock_type):
    wait_until(lambda : server.started)
    sock = websocket.WebSocket()
    sock.io_sock.settimeout(1.0)
    sock.connect(ws_address)
    auth = {
        'zmq_conn_string' : zmq_conn_string,
        'socket_type' : sock_type
        }
    auth = simplejson.dumps(auth)
    sock.send(simplejson.dumps(
        {
            'identity' : 'testidentity',
            'msg_type' : 'connect',
            'content' : auth
        }))
    msg = sock.recv()
    msgobj = simplejson.loads(msg)
    msgobj = simplejson.loads(msgobj['content'])
    assert msgobj['status']        
    return sock
