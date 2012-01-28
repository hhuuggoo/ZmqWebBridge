zmq = {}
zmq.SUB = 2
zmq.REQ = 3
zmq.uuid = function () {
    //from ipython project
    // http://www.ietf.org/rfc/rfc4122.txt
    var s = [];
    var hexDigits = "0123456789ABCDEF";
    for (var i = 0; i < 32; i++) {
        s[i] = hexDigits.substr(Math.floor(Math.random() * 0x10), 1);
    }
    s[12] = "4";  // bits 12-15 of the time_hi_and_version field to 0010
    s[16] = hexDigits.substr((s[16] & 0x3) | 0x8, 1);  // bits 6-7 of the clock_seq_hi_and_reserved to 01
    
    var uuid = s.join("");
    return uuid;
};

zmq.Context = function(ws_conn_string){
    //zmq context proxy.  contains a websocketconnection
    //routes messages to fake zmq sockets on the js side
    this.sockets = {}
    var that = this;
    try {
	this.s = new WebSocket(ws_conn_string);
    }
    catch (e) {
	this.s = new MozWebSocket(ws_conn_string);
    }
    this.s.onmessage = function(msg){
	var msgobj = JSON.parse(msg.data);
	that.sockets[msgobj['identity']]._handle(msgobj['content'])
    }
    this.s.onopen = function(){
	that.connected = true;
	$.map(that.send_buffer, function(x){
	    that.s.send(x);
	});
	that.send_buffer = [];
    }
    this.connected = false;
    this.send_buffer = [];
}
zmq.Context.prototype.Socket = function(socket_type){
    //contexts are also a factory for sockets, just like
    //in normal zeromq
    var fakesocket;
    if (socket_type === zmq.SUB){
	fakesocket = new zmq.SubSocket(this);
    }else{
	fakesocket =  new zmq.ReqSocket(this);
    }
    this.sockets[fakesocket.identity] = fakesocket;
    return fakesocket;
}

zmq.Context.prototype.send = function(msg){
    if (this.connected){
	this.s.send(msg);
    }else{
	this.send_buffer.push(msg);
    }
}

zmq.Socket = function(ctx){
    this.ctx = ctx
    this.identity = zmq.uuid();
}

zmq.Socket.prototype.construct_message = function(msg, msg_type){
    //your message should be a string
    //constructs a message object, as json
    //this will be serialized before it goes to the wire
    if(!msg_type){
	msg_type = 'userlevel'
    }
    return {
	'identity' : this.identity,
	'content' : msg,
	'msg_type' : msg_type
    }
}
zmq.ReqSocket = function(ctx){
    zmq.Socket.call(this, ctx);
    this.reqrep_buffer = [];
    this.busy = false;
    this.socket_type = zmq.REQ;
}
zmq.ReqSocket.prototype = new zmq.Socket();
zmq.ReqSocket.prototype.send = function(msg, callback, msg_type){
    var msgobj = this.construct_message(msg, msg_type)
    this._send(JSON.stringify(msgobj), callback);
}
zmq.ReqSocket.prototype._send = function(msg, callback){
    this.reqrep_buffer.push([msg, callback]);
    if (this.busy){
	return
    }else{
	this._send_buffer();
    }
}
zmq.ReqSocket.prototype._send_buffer = function(){
    if (this.busy || this.reqrep_buffer.length == 0){
	return
    }else{
	this.busy = true;
	this.ctx.send(this.reqrep_buffer[0][0]);
	return
    }
}

zmq.ReqSocket.prototype._handle = function(msg){
    this.busy = false;
    var callback = this.reqrep_buffer[0][1]
    this.reqrep_buffer = this.reqrep_buffer.slice(1);
    callback(msg);
    this._send_buffer();
}

zmq.ReqSocket.prototype.connect = function(zmq_conn_string, auth){
    auth['zmq_conn_string'] = zmq_conn_string;
    auth['socket_type'] = this.socket_type;
    var msg = JSON.stringify(auth)
    var that = this;
    this.send(msg, function(x){
	var status = JSON.parse(x);
	if (status['status'] === 'success'){
	    that.connected = true;
	}else{
	    that.connected = false;
	    //alert ('problem connecting');
	}
    }, 'connect');
}

zmq.SubSocket = function(ctx){
    zmq.ReqSocket.call(this, ctx);
    this.socket_type = zmq.SUB;
}
//prototype from req socket, because we need the auth functionality
zmq.SubSocket.prototype = new zmq.ReqSocket();
zmq.SubSocket.prototype._handle = function(msg){
    //only used for connect
    if (!this.connected){
	zmq.ReqSocket.prototype._handle.call(this, msg);
    }else{
	this.onmessage(msg);
    }
}



zmq.RPCClient = function(socket){
    this.socket = socket;
}
zmq.RPCClient.prototype.rpc = function(funcname, args, kwargs, callback){
    msg = {'funcname' : funcname,
	   'args' : args,
	   'kwargs' : kwargs}
    var wrapped_callback = function (msg){
	var msgobj = JSON.parse(msg);
	callback(msgobj['returnval']);
    }
    this.socket.send(JSON.stringify(msg), wrapped_callback);
}

zmq.PubRPCServer = function(socket){
    this.socket = socket;
    var that = this;
    if (socket){
	socket.onmessage = function(msg){
	    that.handle_pub(msg);
	}
    }
}
zmq.PubRPCServer.prototype.handle_pub = function(msg){
    var msgobj = JSON.parse(msg)
    var funcname = msgobj['funcname']
    var args = msgobj['args'] || [];
    this[funcname].apply(this, args);
}