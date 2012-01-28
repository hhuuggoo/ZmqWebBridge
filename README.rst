============
ZmqWebBridge
============

The point of this project is to allow javascript client code to interact with arbitrary zeromq services in the backend, with minimal server side configuration.  In  general, when people write websocket code, they write alot of application specific web socket code in whichever web framework they are using.  We want to push most of the application logic into generic zmq processes, with the only application code running in the web server being the code necessary to authenticate users and decide who can access which resources.

Zmq Web Bridge, is a project that allows javascript running in the browser to connect to zmq.REP and zmq.PUB  sockets running on a server, via a python gevent proxy.
The javascript client code sets up a websocket, which communicates with the python gevent proxy, which forwards communications to various zmq backends.  This package also provides a basic framework for authentication, to determine who can access which zmq resources.

* you need to know what you're doing before you use this in production, zeromq isn't written for public facing apps, the way most web frameworks are created some possible problems that aren't apparent at first glance

  1.  if a client sends a malformed zmq connection string, your bridge will fail (this failure occurs on the native code side, so we can't catch it in python)
  2.  if you use a REP socket, and you call socket.recv_json(), and some random client in the world is NOT sending you json, it'll bust your REQ REP ping pong cycle.  so you have to handle those types of things accordingly.

* I recently tried to deploy this on another machine, and it would not work with the pyzmq installed there, I tracked it down to some versioning issues which caused XREQs and XREPs not to function properly, reinstalling fresh pyzmq from git (and stable zeromq 2.1) solved the issue.  I'll try adding a test (there are no tests yet) which will tell you if your XREQs and XREPs are working properly

Syntax
------

js reqrep
----------
::

  context = new zmq.Context('wss://localhost:8000/data');
  reqrep = context.Socket(zmq.REQ);
  reqrep.connect('tcp://127.0.0.1:10001', {});

  reqrep2 = context.Socket(zmq.REQ);
  reqrep2.connect('tcp://127.0.0.1:10001', {});
  reqrep.send('hello', function(x){
		       //callback for request
		       console.log(x)
  }
  );
  reqrep2.send('hello', function(x){
      //callback for request
      console.log(x + 'sdf');
      console.log(x + 'sfsf');
  });


js pub sub:
-----------
::

  sub = context.Socket(zmq.SUB);
  sub.onmessage = function(x){
      console.log(['sub', x]);
  }
  sub.connect("tcp://127.0.0.1:10002", {});

sever side python:
generic, zmq code, which is not apart of this framework:

python : your application bridge
--------------------------------
::


  from gevent import pywsgi
  from geventwebsocket.handler import WebSocketHandler
  import bridge
  import simplejson

  logging.basicConfig(level=logging.DEBUG)
  class MyBridgeClass(bridge.BridgeWebProxyHandler):
      def zmq_allowed(self, params):
	  params = simplejson.loads(params)
	  zmq_conn_string = params['zmq_conn_string']
	  socket_type = params['socket_type']
	  return params['username'] == 'hugo'


  class MyWsgiHandler(bridge.WsgiHandler):
      bridge_class = MyBridgeClass
      HWM = 100 #zmq HWM must be set here, and on your server
      def websocket_allowed(self, environ):
	  #you can add logic here to do auth
	  return True

  app = MyWsgiHandler()
  server = pywsgi.WSGIServer(('0.0.0.0', 8000), app.wsgi_handle,
			     # keyfile='/etc/nginx/server.key',
			     # certfile='/etc/nginx/server.crt',
			     handler_class=WebSocketHandler)
  server.serve_forever()

python req rep server, and pub server
-------------------------------------
::

  (this has nothing to do with the bridge, it's just a generic zmq process)
  import zmq
  import time

  c = zmq.Context()
  s = c.socket(zmq.REP)
  s.bind('tcp://127.0.0.1:10001')

  while True:
      msg = s.recv_multipart()
      print 'received', msg
      s.send_multipart(['goober'])

  ------------------
  import zmq
  import time

  c = zmq.Context()
  s = c.socket(zmq.PUB)
  s.bind('tcp://127.0.0.1:10002')
  while(True):
      for c  in  range(100):
	  print c
	  s.send(str(c))
	  time.sleep(1)



bridge code structure
---------------------
ZmqGatewayFactory - returns an existing zeromq gateway if we have one, otherwise
constructs a new onew

WebProxyHandler - generic handler which works with proxy objects, proxies can
register with WebProxyHandler, and deregister with them

* ZmqGateway - proxy handler which handles the zeromq side of things.

  1. SubGateway - sub socket version

  2. ReqGateway - request socket version

* BridgeWebProxyHandler - proxy handler which handles the web socket side of things.
  you have one of these per web socket connection.  it listens on the web
  socket, and when a connection request is received, grabs the appropriate
  zeromq gateway from the factory.  It also registers the proxy with this
  object nad the zeromq gateway

* SocketProxy

  1. ReqSocketProxy

  2. SubSocketProxy

  these proxy objects below are dumb objects.  all they do is manage
  relationships with their reqpective websocket and zeromq gateways.
  the gateways use this object to get to the appropriate opposing gateway
  you have one instance of this, for every fake zeromq socket you have on the
  js side	

=============
RPC Interface
=============


We've also built in an RPC interface

Request Reply
-------------

* Python

  You define functions that you want to be able to call from js.  the functions
  can be called with args, and kwargs.   the return value is passed down
  to the JS callback.  a list of authorized functions is specified for each
  RPC server, if it is None then all functions are fair game.  the can_function
  prefixed  function is called, if it exists, and if it returns false, 
  we don't execute the main function.   This is where you would 
  build in any method level
  authentication

  ::

    class TestRPC(bridgeutils.GeventZMQRPC):
	authorized_functions = ['echo', 'add_user']
	def echo(self, msg):
	    return msg

	def add_user(self, username, password, type='boy'):
	    return {'status' : "success"}

	def can_add_user(self, username, password, type='boy'):
	    return True	 

* JS

  Javascript RPC client is instantiated with an instance of the socket.
  rpc takes 4 arguments, function name, args, kwargs, and the callback.
  the callback gets the object that was returned - any JSON object is 
  supported

  ::

    rpc_client = new zmq.RPCClient(socket);
    rpc_client.rpc('echo', 'hello!', {}, function(response){
						console.log(response);
						});
    rpc_client.rpc('echo', 'hello!', 
    	 	     {type : 'girl'}, 
		   function(response){
                       console.log(response['status']);
		   });


Pub Sub
-------

Pub sub allows the server, to remotely call functions on the client - though 
since the communciation is one way, there is no return value.  Also since
JS does not support key word args, we only support positional arguments

* Python

  ::
    
    rpc_client = bridgeutils.PubSubRPCCLient(socket)
    rpc_client.rpc('add', 1, 2)
    
* JS

  ::

    rpc_server = zmq.PubRPCServer()
    rpc_server.prototype.add = function(first, second){
        console.log(first + second);
    }   


