import zmq
import zmq.jsonapi as jsonapi

class RPCClient(object):
    def __init__(self, socket, timeout=1.0):
        self.socket = socket
        self.timeout = timeout
        
    def rpc(self, funcname, *args, **kwargs):
        msg = {'funcname' : funcname,
               'args' : args}
        self.socket.send(jsonapi.dumps(msg))
        poller = zmq.Poller()
        poller.register(self.socket, zmq.POLLIN)
        socks = dict(poller.poll(timeout=self.timeout))
        if self.socket in socks:
            message = self.socket.recv()
            msgobj = jsonapi.loads(msg)
            return msgobj
        else:
            return None
        
    def run_send(self):
        while True:
            msg = self.queue.get()
            self.socket.send(msg)
        
                       
