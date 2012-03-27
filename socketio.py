from threading import *
import urllib2, urllib
import simplejson as json
import ssl, socket
import time
from websocket_client import create_connection
import traceback

class SocketIO:
   def __init__(S, url, callback, debug=False):
      S.url = url
      S.callback = callback
      S.debug = debug
      S.keepalive_thread = None
      S.thread = None
      S.reconnect = False

      if S.debug:
         import datetime
         now = time.localtime()
         S._debug("%s: SocketIO class started" % (datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')))
         

   def _debug(S, msg):
      if S.debug:
         print msg
      
   def connect(S):
      data = urllib.urlencode({})
      url = 'https://' + S.url + "/1"
      req = urllib2.Request(url, data)
      S._debug(url)
      S._debug("resolving URL...")

      connected = False
      while connected == False:
         try:
            response = urllib2.urlopen(req)
            connected = True
         except urllib2.HTTPError, e:
            print "Error resolving: \"" + url + "\":" + str(e.reason) + ", " + str(e.code)
            print "Sleeping 10 seconds and then trying again..."
            time.sleep(10)
         except urllib2.URLError, e:
            print "Error resolving: \"" + url + "\":" + str(e.reason)
            print "Sleeping 10 seconds and then trying again..."
            time.sleep(10)
            
      S._debug("retrieving URL content...")
      r = response.read().split(':')
      S.heartbeat_interval = int(r[1])
      S._debug('heartbeat:' + str(S.heartbeat_interval))
      if 'websocket' in r[3].split(','):
         S._debug("good: transport 'websocket' supported by socket.io server " + S.url)
         S.id = r[0]
         S._debug("id: " + S.id)
      else:
         print "error: transport 'websocket' NOT supported by socket.io server " + S.url

      response.close()
      
      S.thread = Thread(target=S.thread_func)
      S.thread.daemon = True
      S.thread.start()

   def stop(S):
      S.run = False
      S.ws.close()

   def thread_func(S):
      thread_ident = current_thread().name + ":"
      S._debug(thread_ident + "this is thread_func")
      S._debug('SocketIO: websocket thread started')
      
      my_url = 'wss://' + S.url + "/1/websocket/" + S.id
      S._debug("connecting websocket...")
      S.ws = create_connection(my_url)
      S._debug("connected!")

      S.run = True
      S.reconnect = False
      S.ws.send('1::/mtgox')

      # start keepalive thread
      if (S.keepalive_thread is None or S.keepalive_thread.isAlive() == False):
         S._debug(thread_ident + "no keepalive thread is running. creating new...")
         S.keepalive_thread = Thread(target=S.keepalive_func)
         S.keepalive_thread.daemon = True
         S.keepalive_thread.start()         
      
      msg = S.ws.recv()
      while msg is not None and S.run:
         if msg[:10] == "4::/mtgox:":
            S.callback(S, msg[10:])
         try:
            msg = S.ws.recv()
         except:
            if (S.run == True):
               print thread_ident, "error waiting for message to arrive. closing existing connection..."
               S.run = False
               S.ws.close()
               print thread_ident, '\ttrying reconnect...'
               S.connect()
            if (S.reconnect == True):
               print thread_ident, '\ttrying reconnect...'
               S.connect()
            #as far as I can tell, reraising the exception should make this thread exit
            #  so it's ok if we've create a new one by calling S.connect() above
            S._debug(thread_ident + 'about to raise exception...')
            raise
      else:
         if (S.run == False and S.reconnect == True):
            #this means the keepalive thread function caught an exception, set S.run to False and closed the connection. we should reconnect and exit this thread
            print thread_ident, 'trying reconnect...'
            S.connect()
            raise SystemExit
         if (msg is None and S.run == True):
            print thread_ident, "recv() returned empty message. connection is broken. let's try to close this connection and reconnect, and then exit this thread."
            S.run = False
            S.ws.close()
            print thread_ident, '\ttrying reconnect...'
            S.connect()
            raise SystemExit
         
   def keepalive_func(S):
      thread_ident = current_thread().name + ":"
      while S.run:
         try:
            S.ws.send('2::');
            print thread_ident, "just sent keepalive message"
         except:
            if S.run:
               #we can't do a reconnect in this thread. if we do that, multiple thread_funcs will exist
               print thread_ident, 'error sending keepalive socket.io, closing connection and waiting for thread_func to reconnect...'
               S.run = False
               S.reconnect = True #we use this variable to signal to thread_func that it should reconnect
               S.ws.close()
            else:
               print thread_ident, 'exiting socket.io keepalive thread'
            raise
         print thread_ident, "sleeping %d seconds..." % (S.heartbeat_interval)
         time.sleep(S.heartbeat_interval)
      print thread_ident, "while loop over. exiting."

   def unsubscribe(S, channel_id):
      S.ws.send('4::/mtgox:{"op":"unsubscribe","channel":"%s"}' % channel_id)
         
def test_callback(S, msg):
   import ast
   print 'msg: ', msg
   #convert received message string into dictionary
   msg_dict = ast.literal_eval(msg)
   #print msg_dict
   if msg_dict['op'] == 'subscribe':
      if msg_dict['channel'] == 'd5f06780-30a8-4a48-a2f8-7ed181b4a13f' or msg_dict['channel'] == '24e67e0d-1cad-4cc0-9e7a-f8523ef460fe':
         S.unsubscribe(msg_dict['channel'])

# testcase
if False:
   sio = SocketIO('socketio.mtgox.com/socket.io', test_callback, True)
   sio.connect()
   #time.sleep(
   time.sleep(100)