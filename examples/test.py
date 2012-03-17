import gevent
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler
import logging
import bridge
import simplejson
logging.basicConfig(level=logging.DEBUG)
class MyBridgeClass(bridge.BridgeWebProxyHandler):
    def zmq_allowed(self, params):
        params = simplejson.loads(params)
        zmq_conn_string = params['zmq_conn_string']
        socket_type = params['socket_type']
        print 'auth', params['username'], params['socket_type']
        return params['username'] == 'hugo'
        

class MyWsgiHandler(bridge.WsgiHandler):
    bridge_class = MyBridgeClass
    def websocket_allowed(self, environ):
        #you can add logic here to do auth
        return True


app = MyWsgiHandler()
server = pywsgi.WSGIServer(('0.0.0.0', 8000), app.wsgi_handle,
                           # keyfile='/etc/nginx/server.key',
                           # certfile='/etc/nginx/server.crt',
                           handler_class=WebSocketHandler)
server.serve_forever()

