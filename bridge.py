from geventwebsocket.handler import WebSocketHandler
from gevent import pywsgi
import gevent
from gevent_zeromq import zmq
import logging
log = logging.getLogger(__name__)
import simplejson
from gevent import spawn

# demo app
class ZmqGatewayFactory(self):
    def __init__(self):
        self.sub_gateways = {}
        self.ctx = zmq.Context()
        
    def get(self, socket_type, zmq_conn_string):
        if (socket_type, zmq_conn_string) in self.sub_gateways:
            gateway =  self.sub_gateways[socket_type, zmq_conn_string]
            #start zmq thread
            spawn(gateway.run)
            return gateway
        else:
            if socket_type == zmq.REQ:
                self.sub_gateways.set((socket_type, zmq_conn_string),
                                      ReqGateway(zmq_conn_string, ctx=self.ctx))
                return self.sub_gateways[socket_type, zmq_conn_string]

class WebProxyHandler(self):
    def __init__(self):
        self.proxies = {}
        
    def register(self, identity, proxy):
        self.proxies[identity] = proxy

    def deregister(self, identity):
        self.proxies.pop(identity)

    def close(self):
        for v in self.proxies.values():
            v.deregister()
            
class ZmqGateway(WebProxyHandler):
    def __init__(self, zmq_conn_string, ctx=None):
        super(ZmqGateway, self).__init__()
        self.zmq_conn_string = zmq_conn_string
        self.ctx = ctx

    def send_proxy(self, identity, msg):
        try:
            self.proxies[identity].send_web(msg)
        #what exception is thrown here?
        except Exception as e:
            log.exception(e)
            self.deregister(k)
            
class SubGateway(self):
    def __init__(self, zmq_conn_string, ctx=None):
        super(SubGateway, self).__init__(zmq_conn_string, ctx=ctx)
        self.s = ctx.Socket(zmq.SUB)
        self.s.connect(zmq_conn_string)

    def run(self):
        while(True):
            msg = self.s.recv()
            for k in self.proxies.keys():
                if v.filter in msg:
                    self.send_proxy(k, msg)

class ReqGateway(self):
    def __init__(self, zmq_conn_string, ctx=None):
        super(SubGateway, self).__init__(zmq_conn_string, ctx=ctx)
        self.s = ctx.Socket(zmq.XREQ)
        self.s.connect(zmq_conn_string)

    def send(self, identity, msg):
        #append null string to front of message, just like REQ
        #embed identity the same way
        self.s.send_multipart([identity, '', msg])
        
    def handle_request(self, msg):
        #strip off the trailing string
        identity = msg[0]
        msg = msg[-1]
        self.send_proxy(identity, msg)

    def run(self):
        while True:
            msg = self.s.recv_multipart()
            self.handle_request(msg)
            
            
class WebSocketHandler(WebProxyHandler):
    
    def __init__(self, ws, gateway_factory):
        super(WebSocketHandler).__init__()
        self.ws = ws
        self.gateway_factory = gateway_factory
        
    def zmq_allowed(self, options):
        return True
    
    def connect(self, identity, content):
        content = simplejson.loads(content);
        zmq_conn_string = content['zmq_conn_string']
        socket_type = content['socket_type']
        if socket_type == zmq.REQ:
            proxy = ReqSocketProxy(self, identity)
        else:
            proxy = SubSocketProxy(self, identity)
        gateway = self.gateway_factory.get(socket_type, zmq_conn_string)
        proxy.register(self, gateway)
        self.register(identity, proxy)
                
    def handle_request(self, msg):
        msg = simplejson.loads(msg)
        
        msg_type = msg.get('msg_type')
        identity = msg.get('identity')
        content = msg.get('content')
        
        if msg_type == 'connect':
            if self.zmq_allowed(msg):
                self.connect(content)
                content = simplejson.dumps({'status' : 'success'})
                self.send(identity, content)
            else:
                content = simplejson.dumps({'status' : 'error'})
                self.send(identity, content)
        else:
            self.send_proxy(identity, content)
            
    def send_proxy(self, identity, content):
        try:
            self.proxies[identity].send_zmq(content)
        #what exception is thrown here?
        except Exception as e:
            log.exception(e)
            self.deregister(k)

    def send(self, identity, msg):
        self.ws.send(simplejson.dumps({'identity' : identity,
                                       'content' : msg}))
    def run(self):
        while True:
            msg = self.ws.receive()
            self.handle_request(msg)
            if msg is None:
                self.close()
                break

    
class SocketProxy(self):
    def __del__(self):
        self.deregister()

    def __init__(self, identity)
        self.identity = identity

    def register(self, wsgateway, zmqgateway):
        self.wsgateway = wsgateway
        self.zmqgateway = zmqgateway
        wsgateway.register(self.identity, self)
        zmqgateway.register(self.identity, self)

    def deregister(self):
        wsgateway.deregister(self.identity)
        zmqgateway.deregister(self.identity)
        
    def send_web(self, msg):
        self.wsgateway.send(self.identity, msg)

    def send_zmq(self, msg):
        self.zmqgateway.send(self.identity, msg)
        
class ReqSocketProxy(SocketProxy):
    socket_type = zmq.REQ

class SubSocketProxy(SocketProxy):
    socket_type = zmq.SUB

class WsgiHandler(object):
    def __init__(self):
        self.zmq_gateway_factory = ZmqGatewayFactory()
        
    def websocket_allowed(self, environ):
        return True
    
    def wsgi_handle(self, environ, start_response):
        if 'wsgi.websocket' in environ and self.websocket_allowed(environ):
            handler = WebSocketHandler(environ['wsgi.websocket'],
                                       self.zmq_gateway_factory)
            handler.run()
        else:
            start_response("404 Not Found", [])
            return []

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    app = WsgiHandler()
    server = pywsgi.WSGIServer(('0.0.0.0', 8000), app.wsgi_handle,
                               keyfile='/etc/nginx/server.key',
                               certfile='/etc/nginx/server.crt',
                               handler_class=WebSocketHandler)
    server.serve_forever()

