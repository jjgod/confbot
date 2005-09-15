##   jabber.py 
##
##   Copyright (C) 2001 Matthew Allum
##
##   This program is free software; you can redistribute it and/or modify
##   it under the terms of the GNU Lesser General Public License as published
##   by the Free Software Foundation; either version 2, or (at your option)
##   any later version.
##
##   This program is distributed in the hope that it will be useful,
##   but WITHOUT ANY WARRANTY; without even the implied warranty of
##   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##   GNU Lesser General Public License for more details.
##


"""\

__intro__

jabber.py is a Python module for the jabber instant messaging protocol.
jabber.py deals with the xml parsing and socket code, leaving the programmer
to concentrate on developing quality jabber based applications with Python.

The eventual aim is to produce a fully featured easy to use library for
creating both jabber clients and servers.

jabber.py requires at least python 2.0 and the XML expat parser module
( included in the standard Python distrubution ).

It is developed on Linux but should run happily on over Unix's and win32.

__Usage__

jabber.py basically subclasses the xmlstream classs and provides the
processing of jabber protocol elements into object instances as well
'helper' functions for parts of the protocol such as authentication
and roster management.

An example of usage for a simple client would be ( only psuedo code !)

<> Read documentation on jabber.org for the jabber protocol.

<> Birth a jabber.Client object with your jabber servers host

<> Define callback functions for the protocol elements you want to use
   and optionally a disconnection.

<> Authenticate with the server via auth method, or register via the
   reg methods to get an account.

<> Call sendInitPresence() and requestRoster()

<> loop over process(). Send Iqs,messages and presences by birthing
   them via there respective clients , manipulating them and using
   the Client's send() method.

<> Respond to incoming elements passed to your callback functions.

<> Find bugs :)


"""

# $Id: jabber.py 22 2005-09-11 06:58:03Z limodou $

import xmlstream
import sha, time
from string import split,find,replace

VERSION = 0.3

False = 0;
True  = 1;

NS_CLIENT     = "jabber:client"
NS_SERVER     = "jabber:server"
NS_AUTH       = "jabber:iq:auth"
NS_REGISTER   = "jabber:iq:register"
NS_ROSTER     = "jabber:iq:roster"
NS_OFFLINE    = "jabber:x:offline"
NS_AGENT      = "jabber:iq:agent"
NS_AGENTS     = "jabber:iq:agents"
NS_DELAY      = "jabber:x:delay"
NS_VERSION    = "jabber:iq:version"
NS_TIME       = "jabber:iq:time"
NS_VCARD      = "vcard-temp"
NS_PRIVATE    = "jabber:iq:private"
NS_SEARCH     = "jabber:iq:search"
NS_OOB        = "jabber:iq:oob"
NS_XOOB       = "jabber:x:oob"
NS_ADMIN      = "jabber:iq:admin"
NS_FILTER     = "jabber:iq:filter"
NS_AUTH_0K    = "jabber:iq:auth:0k"
NS_BROWSE     = "jabber:iq:browse"
NS_EVENT      = "jabber:x:event"
NS_CONFERENCE = "jabber:iq:conference"
NS_SIGNED     = "jabber:x:signed"
NS_ENCRYPTED  = "jabber:x:encrypted"
NS_GATEWAY    = "jabber:iq:gateway"
NS_LAST       = "jabber:iq:last"
NS_ENVELOPE   = "jabber:x:envelope"
NS_EXPIRE     = "jabber:x:expire"
NS_XHTML      = "http://www.w3.org/1999/xhtml"
NS_XDBGINSERT = "jabber:xdb:ginsert"
NS_XDBNSLIST  = "jabber:xdb:nslist"

## Possible constants for Roster class .... hmmm ##
RS_SUB_BOTH    = 0
RS_SUB_FROM    = 1
RS_SUB_TO      = 2

RS_ASK_SUBSCRIBE   = 1
RS_ASK_UNSUBSCRIBE = 0

RS_EXT_ONLINE   = 2
RS_EXT_OFFLINE  = 1
RS_EXT_PENDING  = 0


class Connection(xmlstream.Client):
    """Forms the base for both Client and Component Classes"""
    def __init__(self, host, port, namespace,
                 debug=False, log=False, connection=xmlstream.TCP):
    
        self.iq_hdlrs   = []
        self.msg_hdlrs  = []
        self.pres_hdlrs = []
        
        self.disconnect_hdlr = None
        self._expected = {}
        
        self._id = 0;
        
        self.lastErr = ''
        self.lastErrCode = 0

        xmlstream.Client.__init__(self, host, port, namespace,
                                  debug=debug, log=log,
                                  connection=connection )

    def connect(self):
        """Attempts to connect to the specified jabber server.
           Raises an IOError on failiure"""
        self.DEBUG("jabberpy connect called")
        try:
            xmlstream.Client.connect(self)
        except xmlstream.error, e:
            raise IOError(e)

    def disconnect(self):
        """Safely disconnects from the connected server"""
        self.send(Presence(type='unavailable'));
        xmlstream.Client.disconnect(self)

    def send(self, what):
        """Sends a jabber protocol element (Node) to the server"""
        xmlstream.Client.write(self,unicode(what))

    def dispatch(self, root_node ):
        """Called internally when a 'protocol element' is recieved.
           builds the relevant jabber.py object and dispatches it
           to a relevant function or callback.
           Also does some processing for roster and authentication
           helper fuctions"""
        
        self.DEBUG("dispatch called")
        if root_node.name == 'message':
    
            self.DEBUG("got message dispatch")
            msg_obj = Message(node=root_node)
            self.messageHandler(msg_obj) 
            
        elif root_node.name == 'presence':

            self.DEBUG("got presence dispatch")
            pres_obj = Presence(node=root_node)
            self.presenceHandler(pres_obj)
            
        elif root_node.name == 'iq':

            self.DEBUG("got an iq");
            iq_obj = Iq(node=root_node)
            if root_node.getAttr('id') and \
               self._expected.has_key(root_node.getAttr('id')):
                self._expected[root_node.getAttr('id')] = iq_obj
            else:
                self.iqHandler(iq_obj)

        else:
            self.DEBUG("whats a tag -> " + root_node.name)

    ## Call back stuff ###

    def setMessageHandler(self, func, type='default'):
        """Sets a the callback func for recieving messages
           Mulitple callback functions can be set which are
           called in succession. A type attribute can also be
           optionally passed so the callback is only called when a
           message of this type is recieved.
           """

        self.msg_hdlrs.append({  type : func }) 

    def setPresenceHandler(self, func, type='default'):
        """Sets a the callback func for recieving presence
           Mulitple callback functions can be set which are
           called in succession. A type attribute can also be
           optionally passed so the callback is only called when a
           presence of this type is recieved.
           """
        ## self.pres_hdlr = func

        self.pres_hdlrs.append({  type : func }) 

    def setIqHandler(self, func, type='default', ns='default'):
        """Sets a the callback func for recieving iq
           Mulitple callback functions can be set which are
           called in succession. A type and namespace attribute
           can also be set so set functions are only called for
           iq elements with these properties.
           """

        self.iq_hdlrs.append({ type : { ns : func } }) 
        
    def setDisconnectHandler(self, func):
        """Set the callback for a disconnect"""
        self.disconnect_hdlr = func

    def messageHandler(self, msg_obj):   ## Overide If You Want ##
        """Called when a message protocol element is recieved - can be
           overidden"""

        output = ''
        for dicts in self.msg_hdlrs:
            if dicts.has_key(msg_obj.getType()):
                if dicts[msg_obj.getType()].func_code.co_argcount == 2:
                    dicts[msg_obj.getType()](self, msg_obj)
                else:
                    output = dicts[msg_obj.getType()](self, msg_obj, output)
            elif dicts.has_key('default'):
                if dicts['default'].func_code.co_argcount == 2:
                    dicts['default'](self, msg_obj)
                else:
                    output = dicts['default'](self, msg_obj, output)
            else: pass

    def presenceHandler(self, pres_obj): ## Overide If You Want ##
        """Called when a pressence protocol element is recieved - can be
           overidden"""

        output = ''
        for dicts in self.pres_hdlrs:
            if dicts.has_key(pres_obj.getType()):
                if dicts[pres_obj.getType()].func_code.co_argcount == 2:
                    dicts[pres_obj.getType()](self, pres_obj)
                else:
                    output = dicts[pres_obj.getType()](self, pres_obj, output)
            elif dicts.has_key('default'):
                if dicts['default'].func_code.co_argcount == 2:
                    dicts['default'](self, pres_obj)
                else:
                    output = dicts['default'](self, pres_obj, output)
            else: pass

 
    def iqHandler(self, iq_obj):         ## Overide If You Want ##
        """Called when an iq protocol element is recieved - can be
           overidden"""

        for dicts in self.iq_hdlrs: ## do stackables to check ##
            if dicts.has_key(iq_obj.getType()):
                if dicts[iq_obj.getType()].has_key(iq_obj.getQuery()):
                    dicts[iq_obj.getType()][iq_obj.getQuery()](self, iq_obj)
                else:
                    dicts[iq_obj.getType()]['default'](self, iq_obj)
            elif dicts.has_key('default'): 
                dicts['default']['default'](self, iq_obj)
            else: pass


    def disconnected(self):
        """Called when a network error occurs - can be overidden"""
        if self.disconnect_hdlr != None: self.disconnect_hdlr(self)


    ## functions for sending element with ID's ##

    def waitForResponse(self, ID, timeout=0):
        """Blocks untils a protocol element with ID id is recieved.
           If an error is recieved or a timeout occurs ( only if timeout attr
           is set, None is returned with lastErr set to the error"""
        ID = unicode(ID)
        self._expected[ID] = None
        then = time.time()
        has_timed_out = False
        ## TODO , add a timeout
        while (not self._expected[ID]) or has_timed_out:
            self.DEBUG("waiting on %s" % unicode(ID))
            self.process(1)
            if timeout and time.time()-then > timeout:
                has_timed_out = True
                
        if has_timed_out:
            self.lastErr = "Timeout"
            return None
        response = self._expected[ID]
        del self._expected[ID]
        if response.getErrorCode():
            self.lastErr     = response.getError()
            self.lastErrCode = response.getErrorCode()
            return None

        return response 

    def SendAndWaitForResponse(self, obj, ID=None):
        """Sends a protocol element object and blocks until a response with
           the same ID is recieved"""
        if ID is None :
            ID = obj.getID()
            if ID is None:
                ID = self.getAnID()
                obj.setID(ID)
        ID = unicode(ID)
        self.send(obj)
        return self.waitForResponse(ID)

    def getAnID(self):
        """Returns a unique ID"""
        self._id = self._id + 1
        return unicode(self._id)
    

class Client(Connection):
    """Class for managing a connection to a jabber server.
    Inherits from the xmlstream Client class"""    
    def __init__(self, host, port=5222, debug=False, log=False,
                 connection=xmlstream.TCP ):
    
        Connection.__init__(self, host, port,'jabber:client', debug, log,
                            connection=connection)
        
        self._roster = Roster()
        self._agents = {}
        self._reg_info = {}
        self._reg_agent = ''

        #xmlstream.Client.__init__(self, host, port,
        #                          'jabber:client', debug, log)

    def connect(self):
        """Attempts to connect to the specified jabber server.
           Raises an IOError on failiure"""
        self.DEBUG("jabberpy connect called")
        try:
            xmlstream.Client.connect(self)
        except xmlstream.error, e:
            raise IOError(e)

    def disconnect(self):
        """Safely disconnects from the connected server"""
        self.send(Presence(type='unavailable'));
        xmlstream.Client.disconnect(self)

    def send(self, what):
        """Sends a jabber protocol element (Node) to the server"""
        xmlstream.Client.write(self,unicode(what))

    def sendInitPresence(self):
        """Sends an empty presence protocol element to the
           server. Used to 'tell' the server your online"""
        p = Presence()
        self.send(p);
        
    def dispatch(self, root_node ):
        """Called internally when a 'protocol element' is recieved.
           builds the relevant jabber.py object and dispatches it
           to a relevant function or callback.
           Also does some processing for roster and authentication
           helper fuctions"""
        
        self.DEBUG("dispatch called")
        if root_node.name == 'message':
    
            self.DEBUG("got message dispatch")
            msg_obj = Message(node=root_node)
            self.messageHandler(msg_obj) 
            
        elif root_node.name == 'presence':

            self.DEBUG("got presence dispatch")
            pres_obj = Presence(node=root_node)

            who = unicode(pres_obj.getFrom())
            type = pres_obj.getType()
            self.DEBUG("presence type is %s" % type)
            if type == 'available' or not type:
                self.DEBUG("roster setting %s to online" % who)
                self._roster._setOnline(who,'online')
                self._roster._setShow(who,pres_obj.getShow())
                self._roster._setStatus(who,pres_obj.getStatus())
            elif type == 'unavailable':
                self._roster._setOnline(who,'offline')
                self._roster._setShow(who,pres_obj.getShow())
                self._roster._setStatus(who,pres_obj.getStatus())
            else:
                pass
            self.presenceHandler(pres_obj)

            
        elif root_node.name == 'iq':

            self.DEBUG("got an iq");
            iq_obj = Iq(node=root_node)
            queryNS = iq_obj.getQuery()

            ## Tidy below up !! ##
            type = root_node.getAttr('type')
            
            if queryNS:

                if queryNS == NS_ROSTER and ( type == 'result' \
                                             or type == 'set' ): 

                    for item in iq_obj.getQueryNode().getChildren():
                        jid  = item.getAttr('jid')
                        name = item.getAttr('name')
                        sub  = item.getAttr('subscription')
                        ask  = item.getAttr('ask')
                        if jid:
                            if sub == 'remove' or sub == 'none':
                                self._roster._remove(jid)
                            else:
                                self._roster._set(jid=jid,name=name,
                                                  sub=sub,ask=ask)
                        else:
                            self.DEBUG("roster - jid not defined ?")
                        
                elif queryNS == NS_REGISTER and type == 'result':

                        self._reg_info = {}
                        for item in iq_obj.getQueryNode().getChildren():
                            self._reg_info[item.getName()] = item.getData() 
                    
                elif queryNS == NS_AGENTS and type == 'result':

                        self.DEBUG("got agents result")
                        self._agents = {}
                        for agent in iq_obj.getQueryNode().getChildren():
                            if agent.getName() == 'agent': ## hmmm
                                self._agents[agent.getAttr('jid')] = {}
                                for info in agent.getChildren():
                                    self._agents[agent.getAttr('jid')]\
                                         [info.getName()] = info.getData()
                else: pass

                
            if root_node.getAttr('id') and \
               self._expected.has_key(root_node.getAttr('id')):
                self._expected[root_node.getAttr('id')] = iq_obj
            else:
                self.iqHandler(iq_obj)

        else:
            self.DEBUG("whats a tag -> " + root_node.name)


    def auth(self,username,passwd,resource):
        """Authenticates and logs in to the specified jabber server
           Automatically selects the 'best' authentication method
           provided by the server.
           Supports plain text, deigest and zero-k authentication"""

        auth_get_iq = Iq(type='get')
        auth_get_iq.setID('auth-get')
        q = auth_get_iq.setQuery('jabber:iq:auth')
        q.insertTag('username').insertData(username)
        self.send(auth_get_iq)
        
        auth_response = self.waitForResponse("auth-get")
        if auth_response is not None:
            auth_ret_node = auth_response.asNode()
        else:
            return False
        auth_ret_query = auth_ret_node.getTag('query')
        self.DEBUG("auth-get node arrived!")

        auth_set_iq = Iq(type='set')
        auth_set_iq.setID('auth-set')
        
        q = auth_set_iq.setQuery('jabber:iq:auth')
        q.insertTag('username').insertData(username)
        q.insertTag('resource').insertData(resource)

        if auth_ret_query.getTag('token'):
            
            token = auth_ret_query.getTag('token').getData()
            seq = auth_ret_query.getTag('sequence').getData()
            self.DEBUG("zero-k authentication supported")
            hash = sha.new(sha.new(passwd).hexdigest()+token).hexdigest()
            for foo in xrange(int(seq)): hash = sha.new(hash).hexdigest()
            q.insertTag('hash').insertData(hash)

        elif auth_ret_query.getTag('digest'):

            self.DEBUG("digest authentication supported")
            digest = q.insertTag('digest')
            digest.insertData(sha.new(
                self.getIncomingID() + passwd).hexdigest() )
        else:
            self.DEBUG("plain text authentication supported")
            q.insertTag('password').insertData(passwd)
            
        iq_result = self.SendAndWaitForResponse(auth_set_iq)

        if iq_result.getError() is None:
            return True
        else:
           self.lastErr     = iq_result.getError()
           self.lastErrCode = iq_result.getErrorCode()
           # raise error(iq_result.getError()) ?
           return False

    ## Roster 'helper' func's - also see the Roster class ##

    def requestRoster(self):
        """requests the roster from the server and returns a
        Roster() class instance."""
        rost_iq = Iq(type='get')
        rost_iq.setQuery('jabber:iq:roster')
        self.SendAndWaitForResponse(rost_iq)
        self.DEBUG("got roster response")
        self.DEBUG("roster -> %s" % unicode(self._agents))
        return self._roster

    def getRoster(self):
        """Returns the current Roster() class instance. Does
        not contect the server."""
        return self._roster

    def removeRosterItem(self,jid):
        """Removes an item with Jabber ID jid from both the
        servers roster and the local interenal Roster()
        instance"""
        rost_iq = Iq(type='set')
        q = rost_iq.setQuery('jabber:iq:roster').insertTag('item')
        q.putAttr('jid', unicode(jid))
        q.putAttr('subscription', 'remove')
        self.SendAndWaitForResponse(rost_iq)
        print 'sendandwait'
        return self._roster

    ## Registration 'helper' funcs ##
    
    def requestRegInfo(self,agent=None):
        """Requests registration info from the server.
        returns a dict of required values."""
        if agent: agent = agent + '.'
        if agent is None: agent = ''
        self._reg_info = {}
        self.DEBUG("agent -> %s, _host -> %s" % ( agent ,self._host))
        reg_iq = Iq(type='get', to = agent + self._host)
        reg_iq.setQuery('jabber:iq:register')
        self.DEBUG("got reg response")
        self.DEBUG("roster -> %s" % unicode(self._agents))
        return self.SendAndWaitForResponse(reg_iq)        

    def getRegInfo(self):
        """Returns the last requested register dict."""
        return self._reg_info

    def setRegInfo(self,key,val):
        """Sets a name/value attribute. Note: requestRegInfo must be
           called before setting."""
        self._reg_info[key] = val

    def sendRegInfo(self, agent=None):
        """Sends the populated register dict back to the server"""
        if agent: agent = agent + '.'
        if agent is None: agent = ''
        reg_iq = Iq(to = agent + self._host, type='set')
        q = reg_iq.setQuery('jabber:iq:register')
        for info in self._reg_info.keys():
            q.insertTag(info).putData(self._reg_info[info])
        return self.SendAndWaitForResponse(reg_iq)

    ## Agent helper funcs ##

    def requestAgents(self):
        """Requests a list of available agents. returns a dict of
        agents and info"""
        self._agents = {}
        agents_iq = Iq(type='get')
        agents_iq.setQuery('jabber:iq:agents')
        self.SendAndWaitForResponse(agents_iq)
        self.DEBUG("got agents response")
        self.DEBUG("agents -> %s" % unicode(self._agents))
        return self._agents


class Protocol:
    """Base class for jabber 'protocol elements' - messages, presences and iqs.
       Implements methods that are common to all these"""
    def __init__(self):
        self._node = None

    def asNode(self):
        """returns an xmlstreamnode representation of the protocol element"""
        return self._node
    
    def __str__(self):
        return self._node.__str__()

    def getTo(self):
        "Returns a JID object of the to attr of the element" 
        try: return JID(self._node.getAttr('to'))
        except: return None
        
    def getFrom(self):
        "Returns a JID object of the from attribute of the element"
        return JID(self._node.getAttr('from'))
        #except: return None

    def getType(self):
        "Returns the type attribute of the protocol element"
        try: return self._node.getAttr('type')
        except: return None

    def getID(self):
        "Returns the ID attribute of the protocol element"
        try: return self._node.getAttr('id')
        except: return None

    def setTo(self,val):
        "Sets the to JID of the protocol element"
        self._node.putAttr('to', unicode(val))

    def setFrom(self,val):
        "Sets the from JID of the protocol element"
        self._node.putAttr('from', unicode(val))

    def setType(self,val):
        "Sets the type attribute of the protocol element"
        self._node.putAttr('type', val)

    def setID(self,val):
        "Sets the ID of the protocol element"
        self._node.putAttr('id', val)

    def getX(self,index=None):
        "returns the x namespace, optionally passed an index if multiple tags"
        ## TODO make it work for multiple x nodes
        try: return self._node.getTag('x').namespace
        except: return None

    def setX(self,namespace,index=None):
        """Sets the name space of the x tag. It also creates the node
        if it doesn't already exist"""
        ## TODO make it work for multiple x nodes
        x = self._node.getTag('x')
        if x:
            x.namespace = namespace
        else:
            x = self._node.insertTag('x')
            x.setNamespace(namespace)
        return x

    def setXPayload(self, payload):
        """Sets the Child of an x tag. Can be a Node instance or a
        XML document"""
        x = self._node.insertTag('x')

        if type(payload) == type('') or type(payload) == type(u''):
                payload = xmlstream.NodeBuilder(payload).getDom()

        x.kids = [] # should be a method for this realy 
        x.insertNode(payload)
                
    def getXPayload(self, val=None):
        """Returns the x tags payload as a Node instance"""
        nodes = []
        if val is not None:
            if type(val) == type(""):
                for xnode in self._node.getTags('x'):
                    if xnode.getNamespace() == val: nodes.append(xnode.kids[0])
                return nodes
            else:
                try: return self._node.getTags('x')[val].kids[0]
                except: return None

        for xnode in self._node.getTags('x'):
            nodes.append(xnode.kids[0])
        return nodes
    
    def getXNode(self, val=None):
        """Returns the x Node instance. If there are multiple tags
           the first Node is returned. For multiple X nodes use getXNodes
           or pass an index integer value or namespace string to getXNode
           and if a match is found it will be returned"""
        if val is not None:
            nodes = []
            if type(val) == type(""):
                for xnode in self._node.getTags('x'):
                    if xnode.getNamespace() == val: nodes.append(xnode)
                return nodes
            else:
                try: return self._node.getTags('x')[val]
                except: return None
        else:
            try: return self._node.getTag('x')
            except: return None

    def getXNodes(self, val=None):
        """Returns a list of X nodes"""
        try: return self._node.getTags('x')[val]
        except: return None

    def setXNode(self, val=''):
        """Sets the x tags data - just text"""
        self._node.insertTag('x').putData(val)

    def fromTo(self):
        """Swaps the element from and to attributes.
           Not any use with Clients as Server sets from."""
        tmp = self.getTo()
        self.setTo(self.getFrom())
        self.setFrom(tmp)

    __repr__ = __str__

    def setNode(self, node):
        self._node.insertNode(node)



class Message(Protocol):
    """Builds on the Protocol class to provide an interface for sending
       message protocol elements"""
    def __init__(self, to=None, body=None, node=None):
        if node:
            self._node = node
        else:
            self._node = xmlstream.Node(tag='message')
        if to: self.setTo(unicode(to))
        if body: self.setBody(body)
        
    def getBody(self):
        "Returns the message body."
        body = self._node.getTag('body')
        try: return self._node.getTag('body').getData()
        except: return None

    def getSubject(self): 
        "Returns the messages subject."
        try: return self._node.getTag('subject').getData()
        except: return None

    def getThread(self):
        "Returns the messages thread ID."
        try: return self._node.getTag('thread').getData()
        except: return None
        
    def getError(self):
        "Returns the messgaes Error string, if any"
        try: return self._node.getTag('error').getData()
        except: return None

    def getErrorCode(self):
        "Returns the messgaes Error Code, if any"
        try: return self._node.getTag('error').getAttr('code')
        except: return None

    def getTimestamp(self):
        "Not yet implemented"
        pass

    def setBody(self,val):
        "Sets the message body text."
        body = self._node.getTag('body')
        if body:
            body.putData(val)
        else:
            body = self._node.insertTag('body').putData(val)
        active = self._node.getTag('active')
        if not active:
            active = self._node.insertTag('active')
            active.putAttr('xmlns', "http://jabber.org/protocol/chatstates")
            
    def setSubject(self,val):
        "Sets the message subject text."
        subj = self._node.getTag('subject')
        if subj:
            subj.putData(val)
        else:
            self._node.insertTag('subject').putData(val)

    def setThread(self,val):
        "Sets the message thread ID."
        thread = self._node.getTag('thread')
        if thread:
            thread.putData(val)
        else:
            self._node.insertTag('thread').putData(val)

    def setError(self,val,code):
        "Sets the message error text"
        err = self._node.getTag('error')
        if err:
            err.putData(val)
        else:
            err = self._node.insertTag('thread').putData(val)
        err.setAttr('code',unicode(code))

    def setTimestamp(self,val):
        "Not yet implemented"
        pass

    def build_reply(self, reply_txt=''):
        """Returns a new Message object as a reply to its self.
        The reply message, has the to and type automatically
        set."""
        m = Message(to=self.getFrom(), body=reply_txt)
        if not self.getType() == None:
            m.setType(self.getType())  
        t = self.getThread()
        if t: m.setThread(t)
        return m



class Presence(Protocol):
    """Class for creating and managing jabber <presence> protocol
    elements"""
    def __init__(self, to=None, type=None, node=None):
        if node:
            self._node = node
        else:
            self._node = xmlstream.Node(tag='presence')
        if to: self.setTo(unicode(to))
        if type: self.setType(type)


    def getStatus(self):
        """Returns the presence status"""
        try: return self._node.getTag('status').getData()
        except: return None

    def getShow(self):
        """Returns the presence show"""
        try: return self._node.getTag('show').getData()
        except: return None

    def getPriority(self):
        """Returns the presence priority"""
        try: return self._node.getTag('priority').getData()
        except: return None
    
    def setShow(self,val):
        """Sets the presence show"""
        show = self._node.getTag('show')
        if show:
            show.putData(val)
        else:
            self._node.insertTag('show').putData(val)

    def setStatus(self,val):
        """Sets the presence status"""
        status = self._node.getTag('status')
        if status:
            status.putData(val)
        else:
            self._node.insertTag('status').putData(val)

    def setPriority(self,val):
        """Sets the presence priority"""
        pri = self._node.getTag('priority')
        if pri:
            pri.putData(val)
        else:
            self._node.insertTag('priority').putData(val)
            

class Iq(Protocol): 
    """Class for creating and managing jabber <iq> protocol
    elements"""

    def __init__(self, to='', type=None, node=None):
        if node:
            self._node = node
        else:
            self._node = xmlstream.Node(tag='iq')
        if to: self.setTo(to)
        if type: self.setType(type)

    def getError(self):
        """Returns the Iq's error string, if any"""
        try: return self._node.getTag('error').getData()
        except: return None

    def getErrorCode(self):
        """Returns the Iq's error code, if any"""
        try: return self._node.getTag('error').getAttr('code')
        except: return None

    def setError(self,val,code):
        """Sets an Iq's error string and code"""
        err = self._node.getTag('error')
        if err:
            err.putData(val)
        else:
            err = self._node.insertTag('error')
            err.putData(val)
        err.putAttr('code',unicode(code))


    def getQuery(self):
        "returns the query namespace"
        try: return self._node.getTag('query').namespace
        except: return None

    def setQuery(self,namespace):
        """Sets a querys namespace, also inserts a query tag if
        it doesn't already exist"""
        q = self._node.getTag('query')
        if q:
            q.namespace = namespace
        else:
            q = self._node.insertTag('query')
            q.setNamespace(namespace)
        return q

    def setQueryPayload(self, payload):
        """Sets a Iq's query payload. Payload can be either a Node
        structure or a valid xml document. The query tag is automatically
        inserted if it doesn't already exist"""
        q = self.getQueryNode()

        if q is None:
            q = self._node.insertTag('query')

        if type(payload) == type('') or type(payload) == type(u''):
                payload = xmlstream.NodeBuilder(payload).getDom()

        q.kids = []
        q.insertNode(payload)
                
    def getQueryPayload(self):
        """Returns the querys payload as a Node instance"""
        q = self.getQueryNode()
        if q:
            return q.kids[0]
        return None
    
    def getQueryNode(self):
        """Returns any textual data contained by the query tag"""
        try: return self._node.getTag('query')
        except: return None

    def setQueryNode(self, val):
        """Sets textual data contained by the query tag"""
        q = self._node.getTag('query')
        if q:
            q.putData(val)
        else:
            self._node.insertTag('query').putData(val)

class Roster:
    """A Class for simplifying roster management. Also tracks roster
       items availability"""
    def __init__(self):
        self._data = {}
        ## unused for now ... ##
        self._lut = { 'both':RS_SUB_BOTH,
                      'from':RS_SUB_FROM,
                      'to':RS_SUB_TO }

    def getStatus(self, jid): ## extended
        """Gets the status for a Roster item with JID jid"""
        jid = unicode(jid) 
        if self._data.has_key(jid):
            return self._data[jid]['status']
        return None

    def getShow(self, jid):   ## extended
        """Gets the show for a Roster item with JID jid"""
        jid = unicode(jid) 
        if self._data.has_key(jid):
            return self._data[jid]['show']
        return None

    def getOnline(self,jid):  ## extended
        """Gets the online status for a Roster item with JID jid"""
        jid = unicode(jid) 
        if self._data.has_key(jid):
            return self._data[jid]['online']
        return None
    
    def getSub(self,jid):
        """Gets the subscription status for a Roster item with JID jid"""
        jid = unicode(jid) 
        if self._data.has_key(jid):
            return self._data[jid]['sub']
        return None

    def getName(self,jid):
        """Gets the 'name' for a Roster item with JID jid"""
        jid = unicode(jid) 
        if self._data.has_key(jid):
            return self._data[jid]['name']
        return None

    def getAsk(self,jid):
        """Gets the 'ask' status for a Roster item with JID jid"""
        jid = unicode(jid) 
        if self._data.has_key(jid):
            return self._data[jid]['ask']
        return None

    def getSummary(self):
        """Returns a list of basic ( no resource ) JID's with there
           'availability' - online, offline, pending """
        to_ret = {}
        for jid in self._data.keys():
            to_ret[jid] = self._data[jid]['online']
        return to_ret

    def getJIDs(self):
        """Returns a list of JID instances of Roster entries"""
        to_ret = [];
        for jid in self._data.keys():
            to_ret.append(JID(jid))
        return to_ret

    def getRaw(self):
        """Returns the internal data representation of the roster"""
        return self._data

    def isOnline(self,jid):
        """Returns TRUE if the jid is online, FALSE if not"""
        jid = unicode(jid)
        if self.getOnline(jid) != 'online':
            return False
        else:
            return True
    
    def _set(self,jid,name,sub,ask): # meant to be called by actual iq tag
        """Used internally - private"""
        jid = unicode(jid) # just in case
        online = 'offline'
        if ask: online = 'pending'
        if self._data.has_key(jid): # update it
            self._data[jid]['name'] = name
            self._data[jid]['ask'] = ask
            self._data[jid]['sub'] = sub
        else:
            self._data[jid] = { 'name': name, 'ask': ask, 'sub': sub,
                                'online': online, 'status': None, 'show': None} 
    def _setOnline(self,jid,val):
        """Used internally - private"""
        jid = unicode(jid) 
        if self._data.has_key(jid):
            self._data[jid]['online'] = val
        else:                      ## fall back 
            jid_basic = JID(jid).getStripped()
            if self._data.has_key(jid_basic):
                self._data[jid_basic]['online'] = val

    def _setShow(self,jid,val):
        """Used internally - private"""
        jid = unicode(jid) 
        if self._data.has_key(jid):
            self._data[jid]['show'] = val 
        else:                      ## fall back 
            jid_basic = JID(jid).getStripped()
            if self._data.has_key(jid_basic):
                self._data[jid_basic]['show'] = val


    def _setStatus(self,jid,val):
        """Used internally - private"""
        jid = unicode(jid) 
        if self._data.has_key(jid):
            self._data[jid]['status'] = val
        else:                      ## fall back 
            jid_basic = JID(jid).getStripped()
            if self._data.has_key(jid_basic):
                self._data[jid_basic]['status'] = val


    def _remove(self,jid):
        """Used internally - private"""
        if self._data.has_key(jid): del self._data[jid]

class JID:
    """A Simple calss for managing jabber users id's """
    def __init__(self, jid='', node='', domain='', resource=''):
        if jid:
            if find(jid, '@') == -1:
                self.node = ''
            else:
                bits = split(jid, '@')
                self.node = bits[0]
                jid = bits[1]
                
            if find(jid, '/') == -1:
                self.domain = jid
                self.resource = ''
            else:
                self.domain, self.resource = split(jid, '/',1) 
        else:
            self.node = node
            self.domain = domain
            self.resource = resource

    def __str__(self):
        try:
            jid_str = ''
            if self.node: jid_str = jid_str + self.node + '@'
            if self.domain: jid_str = jid_str + self.domain
            if self.resource: jid_str = jid_str +'/'+ self.resource
            return jid_str
        except:
            return ''

    __repr__ = __str__

    def getNode(self):
        """Returns JID Node as string"""
        return self.node
    def getDomain(self):
        """Returns JID domain as string"""
        return self.domain
    def getResource(self):
        """Returns JID resource as string"""
        return self.resource

    def setNode(self,val):
        """Sets JID Node from string"""
        self.node = val
    def setDomain(self,val):
        """Sets JID domain from string"""
        self.domain = val
    def setResource(self,val):
        """Sets JID resource from string"""
        self.resource = val

    def getStripped(self):
        """returns a jid string with no resource"""
        jid_str = ''
        if self.node: jid_str = jid_str + self.node + '@'
        if self.domain: jid_str = jid_str + self.domain
        return jid_str

## component types

## Accept  jabber:component:accept
## Connect jabber:component:connect
## Execute jabber:component:execute

class Component(Connection):
    """docs to come soon... """
    def __init__(self, host, port=5222, connection=xmlstream.TCP,
                 debug=False, log=False, ns='jabber:component:accept'):

        self._auth_OK = False

        Connection.__init__(self, host, port,
                            namespace=ns,
                            debug=debug,
                            log=log,
                            connection=connection)

    def auth(self,secret):
        """will disconnect on faliaure"""
        self.send( u"<handshake id='1'>%s</handshake>" 
                   % sha.new( self.getIncomingID() + secret ).hexdigest()
                  )
        while not self._auth_OK:
            self.DEBUG("waiting on handshake")
            self.process(1)

        return True

    def dispatch(self, root_node):
        """Catch the <handshake/> here"""
        if root_node.name == 'handshake': # check id too ?
            self._auth_OK = True
        Connection.dispatch(self, root_node)


## component protocol elements

class XDB(Protocol):
    
    def __init__(self, to='', frm='', type=None, node=None):
        if node:
            self._node = node
        else:
            self._node = xmlstream.Node(tag='xdb')
        if to: self.setTo(to)
        if type: self.setType(type)
        if frm: self.setFrom(type)


class Log(Protocol):
    ## eg: <log type='warn' from='component'>Hello Log File</log>
    
    def __init__(self, to='', frm='', type=None, node=None):
        if node:
            self._node = node
        else:
            self._node = xmlstream.Node(tag='log')
        if to:   self.setTo(to)
        if type: self.setType(type)
        if frm: self.setFrom(type)

    def setBody(self,val):
        "Sets the log message text."
        self._node.getTag('log').putData(val)

    def setBody(self):
        "Returns the log message text."
        return self._node.getTag('log').getData()


class Server:
    pass


