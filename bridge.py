import gevent
import gevent.monkey
gevent.monkey.patch_all()
from geventwebsocket.handler import WebSocketHandler
from gevent import pywsgi
from gevent_zeromq import zmq
import logging
log = logging.getLogger(__name__)
import simplejson
from gevent import spawn
import Queue
import hashlib

# demo app
class ZmqGatewayFactory(object):
    """ factory returns an existing gateway if we have one,
    or creates a new one and starts it if we don't
    """
    def __init__(self, HWM=100):
        self.gateways = {}
        self.ctx = zmq.Context()
        self.HWM = HWM
        
    def get(self, socket_type, zmq_conn_string):
        if (socket_type, zmq_conn_string) in self.gateways:
            gateway =  self.gateways[socket_type, zmq_conn_string]
            return gateway
        else:
            if socket_type == zmq.REQ:
                log.debug("spawning req socket %s" ,zmq_conn_string) 
                self.gateways[socket_type, zmq_conn_string] = \
                                ReqGateway(zmq_conn_string,
                                           self.HWM,
                                           ctx=self.ctx)
            elif socket_type == zmq.REP:
                log.debug("spawning rep socket %s" ,zmq_conn_string)
                self.gateways[socket_type, zmq_conn_string] = \
                                RepGateway(zmq_conn_string,
                                           self.HWM,
                                           ctx=self.ctx)
            else:
                log.debug("spawning sub socket %s" ,zmq_conn_string) 
                self.gateways[socket_type, zmq_conn_string] = \
                                    SubGateway(zmq_conn_string,
                                               self.HWM,
                                               ctx=self.ctx)
            self.gateways[socket_type, zmq_conn_string].start()
            return self.gateways[socket_type, zmq_conn_string]

    def shutdown(self):
        """
        Close all sockets associated with this context, and then
        terminate the context.
        """
        self.ctx.destroy()

class WebProxyHandler(object):
    """ generic handler which works with proxy objects, proxies can
    register with WebProxyHandler, and deregister with them
    """
    def __init__(self):
        self.proxies = {}
        
    def register(self, identity, proxy):
        self.proxies[identity] = proxy

    def deregister(self, identity):
        try:
            self.proxies.pop(identity)
        except KeyError as e:
            pass

    def close(self):
        for v in self.proxies.values():
            v.deregister()
            
class ZmqGateway(WebProxyHandler):
    """ proxy handler which handles the zeromq side of things.
    """
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
            self.deregister(identity)
            
class SubGateway(ZmqGateway):
    def __init__(self, zmq_conn_string, HWM, ctx=None):
        super(SubGateway, self).__init__(zmq_conn_string, ctx=ctx)
        self.s = ctx.socket(zmq.SUB)
        self.s.setsockopt(zmq.SUBSCRIBE, '');
        if HWM:
            self.s.setsockopt(zmq.HWM, HWM);
        self.s.connect(zmq_conn_string)

    def run(self):
        while(True):
            msg = self.s.recv(copy=True)
            try:
                log.debug('subgateway, received %s', msg)
                for k in self.proxies.keys():
                    if self.proxies[k].msgfilter in msg:
                        self.send_proxy(k, msg)
            except Exception as e:
                log.exception(e)
                continue

    def start(self):
        self.thread = spawn(self.run)
        
class RepGateway(ZmqGateway):
    def __init__(self, zmq_conn_string, HWM, ctx=None):
        super(RepGateway, self).__init__(zmq_conn_string, ctx=ctx)
        self.s = ctx.socket(zmq.XREP)
        if HWM:
            self.s.setsockopt(zmq.HWM, 100);
        self.s.bind(zmq_conn_string)
        self.queue = Queue.Queue()
        self.addresses = {}
        
    def send(self, identity, msg):
        self.queue.put(msg)

    def _send(self, multipart_msg):
        multipart_msg = [str(x) for x in multipart_msg]
        log.debug('sending %s', multipart_msg)
        self.s.send_multipart(multipart_msg)
        
    def run_recv_zmq(self):    
        while True:
            msg = self.s.recv_multipart(copy=True)
            log.debug('received %s', msg)
            try:
                target_ident = msg[-1]
                address_idx = msg.index('')
                address_data = msg[:address_idx]
                hashval = hashlib.sha1(str(address_data)).hexdigest()
                self.addresses[hashval] = address_data
                newmsg = [hashval] + [str(x) for x in \
                                      msg[address_idx:-1]]
                msg = simplejson.dumps(newmsg)
                self.send_proxy(target_ident, msg)
            except:
                pass
            
    def run_send_zmq(self):
        while True:
            try:
                obj = self.queue.get()
                log.debug('ws received %s', obj)
                obj = simplejson.loads(obj)
                address_data = self.addresses[obj[0]]
                self._send(address_data + obj[1:])
            except:
                pass
            
    def start(self):
        self.thread_recv = spawn(self.run_recv_zmq)
        self.thread_send = spawn(self.run_send_zmq)
    
class ReqGateway(ZmqGateway):
    def __init__(self, zmq_conn_string, HWM, ctx=None):
        super(ReqGateway, self).__init__(zmq_conn_string, ctx=ctx)
        self.s = ctx.socket(zmq.XREQ)
        if HWM:
            self.s.setsockopt(zmq.HWM, 100);
        self.s.connect(zmq_conn_string)
        self.queue = Queue.Queue()

    def send(self, identity, msg):
        self.queue.put((identity, msg))

    def _send(self, identity, msg):
        #append null string to front of message, just like REQ
        #embed identity the same way
        self.s.send_multipart([str(identity), '', str(msg)])
        #log.debug('reqgateway, sent %s', msg)

    def handle_request(self, msg):
        #strip off the trailing string
        identity = msg[0]
        msg = msg[-1]
        self.send_proxy(identity, msg)

    def start(self):
        self.thread_recv = spawn(self.run_recv_zmq)
        self.thread_send = spawn(self.run_send_zmq)
        
    def run_recv_zmq(self):
        while True:
            msg = self.s.recv_multipart(copy=True)
            try:
                log.debug('reqgateway, received %s', msg)
                self.handle_request(msg)
            except Exception as e:
                log.exception(e)
                continue

    def run_send_zmq(self):
        while True:
            try:
                obj = self.queue.get()
                identity, msg = obj
                self._send(identity, msg)
            except:
                pass
            
class BridgeWebProxyHandler(WebProxyHandler):
    """
    should rename this to BridgeWebSocketGateway
    proxy handler which handles the web socket side of things.
    you have one of these per web socket connection.  it listens on the web
    socket, and when a connection request is received, grabs the appropriate
    zeromq gateway from the factory.  It also registers the proxy with this
    object nad the zeromq gateway
    """
    
    def __init__(self, ws, gateway_factory):
        super(BridgeWebProxyHandler, self).__init__()
        self.ws = ws
        self.gateway_factory = gateway_factory
        
    def zmq_allowed(self, options):
        return True
    
    def connect(self, identity, content):
        content = simplejson.loads(content);
        zmq_conn_string = content['zmq_conn_string']
        socket_type = content['socket_type']
        if socket_type == zmq.REQ:
            proxy = ReqSocketProxy(identity)
        elif socket_type == zmq.REP:
            proxy = RepSocketProxy(identity)
        else:
            proxy = SubSocketProxy(identity, content.get('msgfilter', ''))
        gateway = self.gateway_factory.get(socket_type, zmq_conn_string)
        proxy.register(self, gateway)
                
    def handle_request(self, msg):
        msg = simplejson.loads(msg)
        
        msg_type = msg.get('msg_type')
        identity = msg.get('identity')
        content = msg.get('content')
        
        if msg_type == 'connect':
            if self.zmq_allowed(content):
                self.connect(identity, content)
                content = simplejson.dumps({'status' : 'success'})
                self.send(identity, content, msg_type='connection_reply')
            else:
                content = simplejson.dumps({'status' : 'error'})
                self.send(identity, content, msg_type='connection_reply')
        else:
            self.send_proxy(identity, content)
            
    def send_proxy(self, identity, content):
        try:
            self.proxies[identity].send_zmq(content)
        #what exception is thrown here?
        except Exception as e:
            log.exception(e)
            self.deregister(identity)

    def send(self, identity, msg, msg_type=None):
        json_msg = {'identity' : identity,
                    'content' : msg}
        if msg_type is not None:
            json_msg['msg_type'] = msg_type
        log.debug('ws sent %s', json_msg)
        self.ws.send(simplejson.dumps(json_msg))
        
    def run(self):
        while True:
            msg = self.ws.receive()
            #log.debug('ws received %s', msg)
            if msg is None:
                self.close()
                break
            self.handle_request(msg)

"""these proxy objects below are dumb objects.  all they do is manage
relationships with their reqpective websocket and zeromq gateways.
the gateways use this object to get to the appropriate opposing gateway
SocketProxy
ReqSocketProxy
SubSocketProxy
you have one instance of this, for every fake zeromq socket you have on the
js side
"""
class SocketProxy(object):

    def __init__(self, identity):
        self.identity = identity

    def register(self, wsgateway, zmqgateway):
        self.wsgateway = wsgateway
        self.zmqgateway = zmqgateway
        wsgateway.register(self.identity, self)
        zmqgateway.register(self.identity, self)

    def deregister(self):
        self.wsgateway.deregister(self.identity)
        self.zmqgateway.deregister(self.identity)
        
    def send_web(self, msg):
        self.wsgateway.send(self.identity, msg)

    def send_zmq(self, msg):
        self.zmqgateway.send(self.identity, msg)
        
class ReqSocketProxy(SocketProxy):
    socket_type = zmq.REQ
    
class RepSocketProxy(SocketProxy):
    socket_type = zmq.REP


class SubSocketProxy(SocketProxy):
    socket_type = zmq.SUB
    def __init__(self, identity, msgfilter):
        super(SubSocketProxy, self).__init__(identity)
        self.msgfilter = msgfilter



"""
Gevent wsgi handler - the main server.  once instnace of this per process
"""
class WsgiHandler(object):
    bridge_class = BridgeWebProxyHandler
    HWM = 100
    def __init__(self):
        self.zmq_gateway_factory = ZmqGatewayFactory(self.HWM)
        
    def websocket_allowed(self, environ):
        return True
    
    def wsgi_handle(self, environ, start_response):
        if 'wsgi.websocket' in environ and self.websocket_allowed(environ):
            handler = self.bridge_class(environ['wsgi.websocket'],
                                        self.zmq_gateway_factory)
            handler.run()
        else:
            start_response("404 Not Found", [])
            return []

    def __del__(self):
        """
        Upon destruction shut down any open sockets, don't rely
        on the garbage collector which can leave sockets
        dangling open.
        """
        self.zmq_gateway_factory.shutdown()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    app = WsgiHandler()
    server = pywsgi.WSGIServer(('127.0.0.1', 8000), app.wsgi_handle,
                               # keyfile='/etc/nginx/server.key',
                               # certfile='/etc/nginx/server.crt',
                               handler_class=WebSocketHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print 'Shutting down gracefully.'
        server.zmq_gateway_factory.shutdown()
