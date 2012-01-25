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

app = bridge.WsgiHandler()
server = pywsgi.WSGIServer(('0.0.0.0', 9000), app.wsgi_handle,
                           handler_class=WebSocketHandler)
server.serve_forever()



