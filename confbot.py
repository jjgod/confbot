#!/usr/bin/env python
# confbot -- a conference bot for google talk.
# Copyright (C) 2005 Perry Lorier (aka Isomer)
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
#      but WITHOUT ANY WARRANTY; without even the implied warranty of
#      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#      GNU General Public License for more details.
# 
#      You should have received a copy of the GNU General Public License
#      along with this program; if not, write to the Free Software
#      Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# You shouldn't have to change anything below this line
# Configuration is now done the first time you run the bot
import socket
import jabber
import xmlstream
import sys
import time
import random
import traceback
import urllib
import ConfigParser

version='1.5'
commandchrs = '/)'

logf = open(time.strftime("%Y%m%d%H%M%S.log"),"w")
xmllogf = open("xmpp.log","w")
last_activity=time.time()
con=None
#xmllogf = sys.stderr

userinfo={}
lastlog = []
hide_status = "0"
private="0"

def getdisplayname(x):
	"Changes a user@domain/resource to a displayable nick (user)"
	x=unicode(x)
	if '/' in x:
		x=x[:x.find("/")]
	if '@' in x and x[x.find('@'):]=="@"+server:
		x=x[:x.find("@")]
	return x

def getjid(x):
	"returns a full jid from a display name"
	if '@' not in x:
		x=x+"@"+server
	return x

def saveconfig():
	"Saves the config to disk"
	if len(sys.argv)>1:
		a=open(sys.argv[1],"w")
	else:
		a=open("confbot.ini","w")
	print >>a,"""; Confbot config written %(date)s by version %(version)s
[general]
account: %(account)s
server: %(server)s
password: %(password)s
topic: %(topic)s
resource: %(resource)s
private: %(private)s
hide_status: %(hide_status)s

; User flags supported:
;  admin: Admin user
;  user: User is allowed to join private rooms
;  banned: User is not allowed to join
[userinfo]""" % {
			"date":time.strftime("%Y-%m-%d %H:%M:%S"),
			"version":version,
			"account":account,
			"server":server,
			"password":password,
			"topic":topic,
			"resource":resource,
			"private":private,
			"hide_status":hide_status,
			}
	for jid,flags in userinfo.items():
		print >>a,"%(jid)s: %(flags)s" % {
			"jid" : jid,
			"flags": " ".join(flags),
			}

def has_userflag(jid,flag):
	"return true if the user is a userflag"
	if not userinfo.has_key(getjid(jid)):
		return 0 # False
	return flag in userinfo[getjid(jid)]

def del_userflag(jid,flag):
	"del an flag, return 0 if they didn't have the flag"
	if not has_userflag(jid,flag):
		return 0
	userinfo[getjid(jid)].remove(flag)
	if userinfo[getjid(jid)]==[]:
		del userinfo[getjid(jid)]
	saveconfig()
	return 1

def add_userflag(jid,flag):
	"add an flag to a user, return 0 if they already have that flag"
	if has_userflag(jid,flag):
		return 0
	if not userinfo.has_key(getjid(jid)):
		userinfo[getjid(jid)]=[flag]
	else:
		userinfo[getjid(jid)].append(flag)
	saveconfig()


def isadmin(jid):	return has_userflag(jid,"admin")
def deladmin(jid):	return del_userflag(jid,"admin")
def addadmin(jid):	return add_userflag(jid,"admin")

def isbanned(jid):	return has_userflag(jid,"banned")
def delban(jid):	return del_userflag(jid,"banned")
def addban(jid):	return add_userflag(jid,"banned")

def isuser(jid):	return has_userflag(jid,"user")
def deluser(jid):	return del_userflag(jid,"user")
def adduser(jid):	return add_userflag(jid,"user")

def sendtoone(who,msg):
	m = jabber.Message(who,msg)
	m.setType('chat')
	con.send(m)

def sendtoall(msg,butnot=[],including=[]):
	global lastlog
	r = con.getRoster()
	print >>logf,time.strftime("%Y-%m-%d %H:%M:%S"),msg.encode("utf-8")
	logf.flush()
	print time.strftime("%Y-%m-%d %H:%M:%S"),msg.encode("utf-8")
	for i in r.getJIDs():
		if getdisplayname(i) in butnot:
			continue
		state=r.getShow(unicode(i))
		if state in ['available','chat','online',None] or getdisplayname(i) in including:
			sendtoone(i,msg)
			time.sleep(.2)
	lastlog.append(msg)
	if len(lastlog)>5:
		lastlog=lastlog[1:]

statuses={}
suppressing=1
def sendstatus(who,txt,msg):
	who = getdisplayname(who)
	if statuses.has_key(who) and statuses[who]==txt:
		return
	statuses[who]=txt
	if not statuses.has_key(who):
		# Suppress initial status
		return
	if suppressing:
		return
	# If we are hiding status changes, skip displaying them
	if not hide_status:
		return
	if msg:
		sendtoall('*** %s is %s (%s)' % (who,txt,msg),including=[who])
	else:
		sendtoall('*** %s is %s' % (who,txt),including=[who])

def boot(jid):
	"Remove a user from the chatroom"
	con.send(jabber.Presence(to=jid, type='unsubscribe'))
	con.send(jabber.Presence(to=jid, type='unsubscribed'))
	if statuses.has_key(getdisplayname(jid)):
		del statuses[getdisplayname(jid)]

def cmd(who,msg):
	if " " in msg:
		cmd,msg=msg.split(" ",1)
	else:
		cmd,msg=msg.strip(),""
	if cmd[:1] in commandchrs:
		cmd=cmd[1:]
	if cmd in ["me"]:
		if msg.strip()=="":
			action=random.choice(['jumps','cries','hops','sighs','farts','keels over and dies','smiles'])
			sendtoone(who,'*** Usage: /me <emote>\nSays an emote as you.  eg "/me %(action)s" shows as "* %(nick)s %(action)s" to everyone else' % {
				"nick" : getdisplayname(who),
				"action" : action,
				})
		else:
			sendtoall('* %s %s' % (getdisplayname(who),msg),butnot=[getdisplayname(who)])
	elif cmd in ["help"]:
		sendtoone(who,"*** Commands: \")help\" \"/me\" \")names\" \")quit\" \")msg\"")
		if isadmin(who.getStripped()):
			sendtoone(who,'*** Admin commands: ")die" ")addadmin" ")deladmin" ")listadmins" ")kick" ")ban" ")unban" ")listbans" ")invite"')
		sendtoone(who,'*** See http://coders.meta.net.nz/~perry/jabber/confbot.php for more details')
	elif cmd in ["names"]:
		r = con.getRoster()
		names=[]
		for i in r.getJIDs():
			state=r.getShow(unicode(i))
			name=getdisplayname(i)
			if isadmin(i.getStripped()):
				name="@%s" % name
			if state in ['available','chat','online',None]:
				names.insert(0,name)
			else:
				names.append('(%s)' % name)
		sendtoone(who,'*** Names: %s' % " ".join(names))
	elif cmd in ["quit","leave","exit"]:
		sendtoall('*** Quit: %s (%s)' % (getdisplayname(who),msg))
		boot(who.getStripped())
	elif cmd in ['msg']:
		if not ' ' in msg:
			sendtoone(who,'*** Usage: )msg <nick> <message>')
		else:
			target,msg = msg.split(' ',1)
			sendtoone(getjid(target),'*%s* %s' % (getdisplayname(who),msg))
			sendtoone(who,'>%s> %s' % (getdisplayname(target),msg))
	elif cmd in ['kick','boot'] and isadmin(who.getStripped()):
		boot(getjid(msg.strip()))
		sendtoall('*** Booted: %s' % msg.strip())
	elif cmd in ['ban'] and isadmin(who.getStripped()):
		boot(getjid(msg.strip()))
		addban(getjid(msg.strip()))
		sendtoall('*** Banned: %s' % msg.strip())
	elif cmd in ['unban'] and isadmin(who.getStripped()):
		if delban(getjid(msg.strip())):
			sendtoone(who,'*** Unbanned: %s' % getjid(msg.strip()))
		else:
			sendtoone(who,'*** %s is not banned' % getjid(msg.strip()))
	elif cmd in ['listbans'] and isadmin(who.getStripped()):
		sendtoone(who,'*** Banned: %s' % " ".join([user for user,data in userinfo.items() if isbanned(user)]))
	elif cmd in ['invite'] and isadmin(who.getStripped()):
		con.send(jabber.Presence(to=getjid(msg.strip()), type='subscribe'))
		adduser(getjid(msg.strip()))
		sendtoone(who,'*** Invited %s' % getjid(msg.strip()))
	elif cmd in ['addadmin'] and isadmin(who.getStripped()):
		addadmin(msg.strip())
		sendtoone(who,'*** Added %s' % getjid(msg.strip()))
		sendtoone(getjid(msg.strip()),'*** %s added you as an admin' % getdisplayname(who))
	elif cmd in ['deladmin'] and isadmin(who.getStripped()):
		if deladmin(msg.strip()):
			sendtoone(who,'*** Removed %s' % getjid(msg.strip()))
			sendtoone(getjid(msg.strip()),'*** %s removed you as an admin' % getdisplayname(who))
		else:
			sendtoone(who,'*** %s is not an admin' % getjid(msg.strip()))
	elif cmd in ['listadmins'] and isadmin(who.getStripped()):
		sendtoone(who,'*** Admins: %s' % " ".join([user for user,data in userinfo.items() if isadmin(user)]))
	elif cmd in ['die'] and isadmin(who.getStripped()):
		if msg.strip():
			sendtoall('*** Admin shutdown by %s (%s)' % (who.getStripped(),msg))
		else:
			sendtoall('*** Admin shutdown by %s' % who.getStripped())
		sys.exit(1)
	elif cmd in ['reload'] and isadmin(who.getStripped()):
		readconfig()
		sendtoone(who,'*** Config reloaded')
	else:
		sendtoone(who,'Unknown command %s' % cmd)

def messageCB(con,msg):
	if msg.getError()!=None:
		if statuses.has_key(getdisplayname(msg.getFrom())):
			sendstatus(unicode(msg.getFrom()),"away","Blocked")
		boot(msg.getFrom().getStripped())
	elif msg.getBody():
		if len(msg.getBody())>1024:
			sendtoall("*** %s is being a moron trying to flood the channel" % (getdisplayname(msg.getFrom())))
		elif msg.getBody()[:1] in commandchrs:
			cmd(msg.getFrom(),msg.getBody())
		else:
			global suppressing,last_activity
			suppressing=0
			last_activity=time.time()
			sendtoall('<%s> %s' % (getdisplayname(msg.getFrom()),msg.getBody()),
				butnot=[getdisplayname(msg.getFrom())],
				)
			if con.getRoster().getShow(msg.getFrom().getStripped()) not in ['available','chat','online',None]:
				sendtoone(msg.getFrom(),'*** Warning: You are marked as "busy" in your client,\nyou will not see other people talk,\nset yourself "available" in your client to see their replies.')
	xmllogf.flush() # just so flushes happen regularly


def presenceCB(con,prs):
	who = unicode(prs.getFrom())
	type = prs.getType()
	# TODO: Try only acking their subscription when they ack ours.
	if type == 'subscribe':
		print "Subscribe from",who,
		if isbanned(prs.getFrom().getStripped()):
			sendtoone(who,'*** You are banned')
			boot(prs.getFrom().getStripped())
			print "Banned"
		elif private and not isuser(prs.getFrom().getStripped()):
			sendtoone(who,'*** This is a private conference bot')
			boot(prs.getFrom().getStripped())
			print "Uninvited"
		else:
			con.send(jabber.Presence(to=who, type='subscribed'))
			con.send(jabber.Presence(to=who, type='subscribe'))
			print "Accepted"
	elif type == 'unsubscribe':
		boot(prs.getFrom().getStripped())
		print "Unsubscribe from",who
	elif type == 'subscribed':
		sendtoone(who,"""Welcome to ConferenceBot %(version)s
By Isomer (Perry Lorier)
This conference bot is set up to allow groups of people to chat.
)help to list commands, )quit to quit
*** Topic: %(topic)s
%(lastlog)s
""" % {
			"version" : version,
			"topic" : topic,
			"lastlog" : "\n".join(lastlog),
			})
		sendstatus(who,'here','joining')
		if userinfo=={}: # No admins?
			# Add this user as the only admin
			addadmin(who.getStripped())
	elif type == 'unsubscribed':
		boot(prs.getFrom().getStripped())
		sendtoall('*** %s has left' % getdisplayname(who))
	elif type == 'available' or type == None:
		show = prs.getShow()
		if show in [None,'chat','available','online']:
			sendstatus(who,'here',prs.getStatus())
		elif show in ['xa']:
			sendstatus(who,'away',prs.getStatus())
		elif show in ['away']:
			sendstatus(who,'away',prs.getStatus())
		elif show in ['dnd']:
			sendstatus(who,'away',prs.getStatus())
		else:
			sendstatus(who,'away',show+" [[%s]]" % prs.getStatus())

	elif type == 'unavailable':
		status = prs.getShow()
		sendstatus(who,'away',status)
	else:
		print "Unknown presence:",who,type

def iqCB(con,iq):
	# reply to all IQ's with an error
	reply=None
	try:
		# Google are bad bad people
		# they don't put their query inside a <query> in <iq>
		reply=jabber.Iq(to=iq.getFrom(),type='error')
		stuff=iq._node.getChildren()
		for i in stuff:
			reply._node.insertNode(i)
		reply.setError('501','Feature not implemented')
		con.send(reply)
	except:
		traceback.print_exc()

def disconnectedCB(con):
	sys.exit(1)

def readoptionorprompt(config,option,description):
	"Read an option from the general section of the config, or prompt for it"
	try:
		return config.get("general",option)
	except ConfigParser.NoOptionError:
		print description
		return raw_input("[%s] " % option)
	except ConfigParser.NoSectionError:
		print description
		return raw_input("[%s] " % option)

def readconfig():
	global account,server,password,topic,resource,private,userinfo
	config = ConfigParser.ConfigParser()
	# Defaults
	if not config.has_section("general"): config.add_section("general")
	config.set("general","server","gmail.com")
	config.set("general","resource","resource")
	config.set("general","private",private)
	config.set("general","hide_status",hide_status)

	if len(sys.argv)>1:
		config.read(sys.argv[1])
	else:
		config.read("confbot.ini")
	account = readoptionorprompt(config,"account","What is the account name of your bot?")
	server = config.get("general","server")
	password = readoptionorprompt(config,"password","What is the password of your bot?")
	topic = readoptionorprompt(config,"topic","Write a short description about your bot")
	resource = config.get("general","resource")
	private = config.getboolean("general","private")
	hide_status = config.getboolean("general","hide_status")

	if config.has_section("userinfo"):
		for i in config.options("userinfo"):
			userinfo[i]=config.get("userinfo",i).split()
	else:
		try:
			adminfile = open("adminlist.txt","r")
			admins=[i.strip() for i in adminfile.readlines()]
			adminfile.close()
			print "Migrating admin list"
			for i in admins:
				userinfo[i]=["admin"]
		except:
			print "Could not open admin file"

readconfig()

print "Connecting"
con = jabber.Client(host=server,debug=False ,log=xmllogf,
                    port=5223, connection=xmlstream.TCP_SSL)
print "Logging in"
con.connect()
con.setMessageHandler(messageCB)
con.setPresenceHandler(presenceCB)
con.setIqHandler(iqCB)
con.setDisconnectHandler(disconnectedCB)
con.auth(account,password,resource)
con.requestRoster()
con.sendInitPresence()
print "Online!"
_roster = con.getRoster()

JID="%s@%s/%s" % (account,server,resource)
last_update=0
last_ping=0
saveconfig()
while 1:
	# We announce ourselves to a url, this url then keeps track of all
	# the conference bots that are running, and provides a directory
	# for people to browse.
	if time.time()-last_update>4*60*60 and not private: # every 4 hours
		args={
			'action':'register',
			'account':"%s@%s" % (account,server),
			'users':len(con.getRoster().getJIDs()),
			'last_activity':time.time()-last_activity,
			'version':version,
			'topic':topic,
			}
		try:
			urllib.urlretrieve('http://coders.meta.net.nz/~perry/jabber/confbot.php?'+urllib.urlencode(args))
			print "Updated directory site"
		except:
			print "Can't reach the directory site"
			traceback.print_exc()
		last_update = time.time()
	# Send some kind of dummy message every few minutes to make sure that
	# the connection is still up, and to tell google talk we're still
	# here.
	if time.time()-last_ping>120: # every 2 minutes
		# Say we're online.
		con.send(jabber.Presence())
	con.process(1)
