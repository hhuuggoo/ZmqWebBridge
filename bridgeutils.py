import zmq
import simplejson as jsonapi
import logging
log = logging.getLogger(__name__)

class RPCClient(object):
    def __init__(self, socket, ident, timeout=1000.0):
        self.socket = socket
        self.ident = ident
        self.timeout = timeout
        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)
        
    def rpc(self, funcname, *args, **kwargs):
        msg = {'funcname' : funcname,
               'args' : args}
        self.socket.send_multipart(['', jsonapi.dumps(msg), self.ident])

        socks = dict(self.poller.poll(timeout=self.timeout))
        if self.socket in socks:
            message = self.socket.recv_multipart()
            print message
            msgobj = jsonapi.loads(message[-1])
            return msgobj.get('returnval', None)
        else:
            return None

class RPCServer(object):
    #none, means we can rpc any function
    #explicit iterable means, only those
    #functions in the iterable can be executed
    #(use a set)
    
    authorized_functions = None 
    
    def __init__(self, reqrep_socket, timeout=1000.0):
        self.reqrep_socket = reqrep_socket
        self.poller = zmq.Poller()
        self.poller.register(self.reqrep_socket, zmq.POLLIN)
        self.kill = False
        self.timeout = timeout
        
    def run_rpc(self):
        while True:
            #the follow code must be wrapped in an exception handler
            #we don't know what we're getting
            socks = dict(self.poller.poll(timeout=self.timeout))
            if self.reqrep_socket in socks:
                try:
                    msg = self.reqrep_socket.recv()
                    msgobj = jsonapi.loads(msg)
                    response_obj = self.get_response(msgobj)
                    response = jsonapi.dumps(response_obj)
                except Exception as e:
                    log.exception(e)
                    response_obj = self.error_obj('unknown ooger')
                    response = jsonapi.dumps(response_obj)
                self.reqrep_socket.send(jsonapi.dumps(response_obj))
            else:
                if self.kill:
                    break

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
