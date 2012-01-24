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
    
class ReqRepTest(unittest.TestCase):
    def setUp(self):
        self.ctx = zmq.Context()
        self.reqrep = self.ctx.socket(zmq.REP)
        self.rr_port = self.reqrep.bind_to_random_port("tcp://127.0.0.1")
        self.app = bridge.WsgiHandler()
        self.server = pywsgi.WSGIServer(('0.0.0.0', 8000), self.app.wsgi_handle,
                                        handler_class=WebSocketHandler)
        self.bridge_thread = spawn(self.server.serve_forever)
        self.rr_thread = spawn(self.rr_func)

    def rr_func(self):
        while True:
            msg = self.reqrep.recv()
            self.reqrep.send(msg)
            
    def tearDown(self):
        self.rr_thread.kill()
        self.bridge_thread.kill()

        
    def test_reqrep(self):
        wait_until(lambda : self.server.started)
        sock = websocket.WebSocket()
        sock.io_sock.settimeout(1.0)
        sock.connect("ws://127.0.0.1:8000/")
        auth = {
            'zmq_conn_string' : 'tcp://127.0.0.1:' + str(self.rr_port),
            'socket_type' : zmq.REQ
            }
        auth = simplejson.dumps(auth)
        sock.send(simplejson.dumps(
            {
                'identity' : 'hello',
                'msg_type' : 'connect',
                'content' : auth
            }))
        msg = sock.recv()
        msgobj = simplejson.loads(msg)
        msgobj = simplejson.loads(msgobj['content'])
        assert msgobj['status']
        sock.send(simplejson.dumps(
            {
                'identity' : 'hello',
                'msg_type' : 'user',
                'content' : 'MYMSG'
            }))
        msg = sock.recv()
        msgobj = simplejson.loads(msg)
        assert msgobj['content'] == 'MYMSG'
        
