
zmq = {}
zmq.SUB = 2
zmq.REQ = 3
zmq.REP = 4
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
	var socket = that.sockets[msgobj['identity']]
	if (socket.connected){
	    socket._handle(msgobj['content']);
	}else if (msgobj['msg_type'] === 'connection_reply'){
	    that.onconnect(socket, msgobj['content']);
	}
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
    
zmq.Context.prototype.connect = function(socket, zmq_conn_string, auth){
    auth['zmq_conn_string'] = zmq_conn_string;
    auth['socket_type'] = socket.socket_type;
    var msg = JSON.stringify(auth)
    var msgobj = socket.construct_message(msg, 'connect')
    msg = JSON.stringify(msgobj);
    this.send(msg);
}
    
zmq.Context.prototype.onconnect = function(socket, msg){
    var msgobj = JSON.parse(msg);
    if (msgobj['status'] === 'success'){
	socket.connected = true;
    }else{
	socket.connected = false;
    }
}

zmq.Context.prototype.Socket = function(socket_type){
    //contexts are also a factory for sockets, just like
    //in normal zeromq
    var fakesocket;
    if (socket_type === zmq.SUB){
	fakesocket = new zmq.SubSocket(this);
    }else if (socket_type === zmq.REQ){
	fakesocket =  new zmq.ReqSocket(this);
    }else if (socket_type === zmq.REP){
	fakesocket =  new zmq.RepSocket(this);
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

zmq.Socket.prototype.connect = function(zmq_conn_string, auth){
    this.ctx.connect(this, zmq_conn_string, auth);
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


zmq.SubSocket = function(ctx){
    zmq.ReqSocket.call(this, ctx);
    this.socket_type = zmq.SUB;
}

//prototype from req socket, because we need the auth functionality
zmq.SubSocket.prototype = new zmq.Socket();
zmq.SubSocket.prototype._handle = function(msg){
    this.onmessage(msg);
}

zmq.RepSocket = function(ctx){
    zmq.ReqSocket.call(this, ctx);
    this.socket_type = zmq.REP;
    this.in_buffer = [];
},

zmq.RepSocket.prototype = new zmq.Socket();

zmq.RepSocket.prototype.send = function(msg){
    //layer adressing information
    var msg = [this.address, '', msg]
    msg = JSON.stringify(msg);
    var msgobj = this.construct_message(msg)
    this.ctx.send(JSON.stringify(msgobj));
    //this is a reply, so now we are no longer busy
    this.busy = false;
    //try to process in_buffer
    this._recv_buffer();
}
zmq.RepSocket.prototype._recv_buffer = function(){
    if (this.busy || this.in_buffer.length == 0){
	return
    }else{
	var msg = this.in_buffer[0];
	this.in_buffer = this.in_buffer.slice(1);

	this.busy = true;
	var msgobj = JSON.parse(msg);
	var address = msgobj[0];
	var content = msgobj[msgobj.length - 1];
	this.address = address;
	this.onmessage(content);
    }
}

zmq.RepSocket.prototype._handle = function(msg){
    this.in_buffer.push(msg);
    this._recv_buffer();
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

zmq.RPCServer = function(socket){
    this.socket = socket;
    var that = this;
    if (socket){
	socket.onmessage = function(msg){
	    that.handle(msg);
	}
    }
}
    
zmq.RPCServer.prototype.handle = function(msg){
    var msgobj = JSON.parse(msg)
    var funcname = msgobj['funcname']
    var args = msgobj['args'] || [];
    try{
	retval = this[funcname].apply(this, args);
    }catch(err){
	retval = err;
    }
    this.socket.send(JSON.stringify({'returnval' : retval}));
}