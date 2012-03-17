import gevent
import gevent.queue
from gevent_zeromq import zmq
import logging
log = logging.getLogger(__name__)
import simplejson
from gevent import spawn
import collections
import logging
import time
log = logging.getLogger('__name__')
jsonapi = simplejson

class GeventZMQRPC(object):
    #none, means we can rpc any function
    #explicit iterable means, only those
    #functions in the iterable can be executed
    #(use a set)
    
    authorized_functions = None 
    
    def __init__(self, reqrep_socket):
        self.reqrep_socket = reqrep_socket

    def run_rpc(self):
        while True:
            try:
                #the follow code must be wrapped in an exception handler
                #we don't know what we're getting
                msg = self.reqrep_socket.recv()
                msgobj = jsonapi.loads(msg)
                response_obj = self.get_response(msgobj)
                response = jsonapi.dumps(response_obj)
                
            except Exception as e:
                log.exception(e)
                response_obj = self.error_obj('unknown error')
                response = jsonapi.dumps(response_obj)
                
            self.reqrep_socket.send(jsonapi.dumps(response_obj))

    def error_obj(self, error_msg):
        return {'status' : 'error',
                'error_msg' : error_msg}
    
    def returnval_obj(self, returnval):
        return {'returnval' : returnval}
    
    def get_response(self, msgobj):
        funcname = msgobj['funcname']
        args = msgobj.get('args', [])
        kwargs = msgobj.get('kwargs', {})
        auth = False
        if self.authorized_functions is not None \
           and funcname not in self.authorized_functions:
            return self.error_obj('unauthorized access')
          
        if hasattr(self, 'can_' + funcname):
            auth = self.can_funcname(*args, **kwargs)
            if not auth:
                return self.error_obj('unauthorized access')
            
        func = getattr(self, funcname)
        retval = func(*args, **kwargs)
        return self.returnval_obj(retval)
        
                       
        
class PubSubRPCClient(object):
    def __init__(self, socket):
        self.socket = socket
        self.queue = gevent.queue.Queue()
        
    def rpc(self, funcname, *args, **kwargs):
        msg = {'funcname' : funcname,
               'args' : args}
        self.queue.put(jsonapi.dumps(msg))

    def run_pub(self):
        while True:
            msg = self.queue.get()
            self.socket.send(msg)
                        

class GeventRPCClient(object):
    def __init__(self, socket, ident, timeout=1.0):
        self.socket = socket
        self.ident = ident
        self.queue = gevent.queue.Queue()
        self.timeout = timeout
        
    def rpc(self, funcname, *args, **kwargs):
        msg = {'funcname' : funcname,
               'args' : args}
        self.socket.send_multipart([jsonapi.dumps(msg), self.ident])
        data = []
        def recv():
            val = self.socket.recv()
            data.append(val)
        recv_t = gevent.spawn(recv)
        recv_t.join(timeout=self.timeout)
        recv_t.kill()
        if len(data) == 1:
            return jsonapi.loads(data[0])['returnval']
        else:
            return None
        
    def run_send(self):
        while True:
            msg = self.queue.get()
            self.socket.send(msg)
        
                       
