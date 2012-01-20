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
    self.unregistered_sockets = {}
    self.sockets = {}
    try {
	this.s = new WebSocket(ws_conn_string);
    }
    catch (e) {
	this.s = new MozWebSocket(ws_conn_string);
    }
    s.onmessage = function(msg){
	var msgobj = JSON.parse(msg);
	this.sockets[msgobj['identity']]._handle(msgobj['content'])
    }
}

zmq.Context.prototype.Socket = function(socket_type){
    //contexts are also a factory for sockets, just like
    //in normal zeromq
    if (socket_type === zmq.SUB){
	return zmq.SubSocket(this);
    }else{
	return zmq.ReqSocket(this);
    }
}

zmq.Socket = function(ctx){
    this.ctx = ctx
    this.identity = zmq.uuid();
}
zmq.Socket.prototype.get_message = function(msg, msg_type){
    //your message should be a string
    //constructs a message object, as json
    //this will be serialized before it goes to the wire
    if(msg_type){
	msg_type = 'userlevel'
    }
    return {
	'identity' : this.identity,
	'content' : msg,
	'msg_type' : msg_type
    }
}
zmq.ReqSocket = function(ctx){
    zmq.Socket.call(this, [ctx]);
    this.reqrep_buffer = [];
    this.busy = false;
    this.socket_type = zmq.REQ;
}
zmq.ReqSocket.prototype = new zmq.Socket();
zmq.ReqSocket.send = function(msg, callback){
    this._send(this.get_message(msg), callback);
}
zmq.ReqSocket._send = function(msg, callback){
    this.reqrep_buffer.push([msg, callback]);
    if (this.busy){
	return
    }else{
	this._send_buffer();
    }
}
zmq.ReqSocket._send_buffer = function(){
    if (this.busy || this.reqrep_buffer.length == 0){
	return
    }else{
	this.busy = true;
	this.ctx.s.send(this.reqrep_buffer[0][0]);
	return
    }
}

zmq.ReqSocket._handle = function(msg){
    this.busy = false;
    var callback = this.reqrep_buffer[0][1]
    this.reqrep_buffer = this.reqrep_buffer.slice(1);
    callback(msg);
    this._send_buffer();
}

zmq.ReqSocket.prototype.connect = function(zmq_conn_string, auth){
    auth['zmq_conn_string'] = zmq_conn_string;
    auth['socket_type'] = this.socket_type;
    var msg = this.get_message(JSON.stringify(auth), 'connect')
    var that = this;
    this.send(msg, function(x){
	var status = JSON.parse(x);
	if (status['status'] === 'success'){
	    that.connected = true;
	}else{
	    that.connected = false;
	    alert ('problem connecting');
	}
    })
}

zmq.SubSocket = function(ctx){
    zmq.ReqSocket.call(this, [ctx]);
}
//prototype from req socket, because we need the auth functionality
zmq.SubSocket.prototype = new zmq.ReqSocket();
zmq.SubSocket._handle = function(msg){
    //only used for connect
    if (!this.connected){
	zmq.ReqSocket._handle.call(this, [msg]);
    }else{
	this.on_message(msg);
    }
}



