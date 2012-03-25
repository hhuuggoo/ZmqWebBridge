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
import test_utils
wait_until = test_utils.wait_until
connect = test_utils.connect
port = 10010
class ReqRepTest(unittest.TestCase):
    def setUp(self):
        self.ctx = zmq.Context()
        self.reqrep = self.ctx.socket(zmq.REP)
        self.rr_port = self.reqrep.bind_to_random_port("tcp://127.0.0.1")
        self.app = bridge.WsgiHandler()
        self.server = pywsgi.WSGIServer(('0.0.0.0', port), self.app.wsgi_handle,
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
        sock = connect(self.server, "ws://127.0.0.1:" + str(port),
                       'tcp://127.0.0.1:' + str(self.rr_port),
                       zmq.REQ)
        sock.send(simplejson.dumps(
            {
                'identity' : 'testidentity',
                'msg_type' : 'user',
                'content' : 'MYMSG'
            }))
        msg = sock.recv()
        msgobj = simplejson.loads(msg)
        assert msgobj['content'] == 'MYMSG'
        

class SubTest(unittest.TestCase):
    def setUp(self):
        self.ctx = zmq.Context()
        self.pub = self.ctx.socket(zmq.PUB)
        self.pub_port = self.pub.bind_to_random_port("tcp://127.0.0.1")
        self.app = bridge.WsgiHandler()
        self.server = pywsgi.WSGIServer(('0.0.0.0', port), self.app.wsgi_handle,
                                        handler_class=WebSocketHandler)
        self.bridge_thread = spawn(self.server.serve_forever)

    def tearDown(self):
        self.bridge_thread.kill()

    def test_sub(self):
        sock = connect(self.server, "ws://127.0.0.1:" + str(port),
                       'tcp://127.0.0.1:' + str(self.pub_port),
                       zmq.SUB)
        self.pub.send('hellohello')
        msg = sock.recv()
        msgobj = simplejson.loads(msg)
        assert msgobj['identity'] == 'testidentity'
        assert msgobj['content'] == 'hellohello'
        self.pub.send('boingyboingy')
        msg = sock.recv()
        msgobj = simplejson.loads(msg)
        assert msgobj['identity'] == 'testidentity'
        assert msgobj['content'] == 'boingyboingy'
        
class ClientRepTest(unittest.TestCase):
    def setUp(self):
        self.ctx = zmq.Context()
        self.reqrep = self.ctx.socket(zmq.REQ)
        self.reqrep.connect("tcp://127.0.0.1:101010")
        self.req_port = 101010
        self.app = bridge.WsgiHandler()
        self.server = pywsgi.WSGIServer(('0.0.0.0', port), self.app.wsgi_handle,
                                        handler_class=WebSocketHandler)
        self.bridge_thread = spawn(self.server.serve_forever)
        self.ws_thread = spawn(self.ws_reqrep)

        
    def tearDown(self):
        self.bridge_thread.kill()
        self.ws_thread.kill()
    
    def ws_reqrep(self):
        sock = connect(self.server, "ws://127.0.0.1:" + str(port),
                       'tcp://127.0.0.1:' + str(self.req_port),
                       zmq.REP)
        while True:
            msg = sock.recv()
            log.debug(msg)
            msgobj = simplejson.loads(msg)
            sock.send(msg)
            
    def test_req_rep(self):
        self.reqrep.send_multipart(['hello', 'testidentity'])
        a = self.reqrep.recv_multipart()
        assert a[0] == 'hello'
