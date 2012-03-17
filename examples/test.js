context = new zmq.Context('ws://localhost:8000/data');
reqrep = context.Socket(zmq.REQ);

reqrep.connect('tcp://127.0.0.1:10001', {'username':'hugo'});

reqrep2 = context.Socket(zmq.REQ);
reqrep2.connect('tcp://127.0.0.1:10001', {'username':'hugo'});
reqrep.send('hello', function(x){console.log(x)});
reqrep2.send('hello', function(x){
    console.log(x + 'sdf');
    console.log(x + 'sfsf');
});
sub = context.Socket(zmq.SUB);
sub.onmessage = function(x){
    console.log(['sub', x]);
}
sub.connect("tcp://127.0.0.1:10002", {'username':'hugo'});

sub2 = context.Socket(zmq.SUB);
sub2.onmessage = function(x){
    console.log(['not alowed!', x]);
}
sub2.connect("tcp://127.0.0.1:10002", {'username':'nonhugo'});


rep = context.Socket(zmq.REP);
reqrep.send('IDENT ' + rep.identity, function(x){console.log(x)});
rep.connect("tcp://127.0.0.1:10003", {'username' : 'hugo'});
rep.onmessage = function(x){
    console.log(x);
    //echo
    rep.send(x)
}
