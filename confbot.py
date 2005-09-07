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
# Limodou
#    Update 2005/09/05:
#      * Multilanguage support
#      * Add debug flag
#      * Add logpath option
#      * Add language option
#      * Add emotes option
#      * Add Chinese translation po file
#      * Add sysprompt option and add systoone systoall function
#      * Add super admin flag
#############################################################################################

import sys
from configobj import ConfigObj
def getdefaultencoding():
	if len(sys.argv)>1:
		conf = ConfigObj(sys.argv[1])
	else:
		conf = ConfigObj("confbot.ini")
	try:
		encoding = conf['general']['language']
	except:
		encoding = ''
	if not encoding:
		import locale
		encoding = locale.getdefaultlocale()[0]
	return encoding

#install gettext process
import gettext
try:
	t = gettext.translation('confbot', 'locale', [getdefaultencoding()])
	t.install(unicode=1)
except:
	gettext.install('confbot', 'locale', 1)

import socket
import jabber
import xmlstream
import time
import random
import traceback
import urllib
import os.path

version=u'1.6'
commandchrs = '/)'

conf = None	#global config object
welcome = _("""Welcome to ConferenceBot %(version)s
By Isomer (Perry Lorier)
This conference bot is set up to allow groups of people to chat.
)help to list commands, )quit to quit
""")

xmllogf = open("xmpp.log","w")
last_activity=time.time()
#xmllogf = sys.stderr
con=None
lastlog = []

def getdisplayname(x):
	"Changes a user@domain/resource to a displayable nick (user)"
	server = conf['general']['server']
	x=unicode(x)
	if '/' in x:
		x = x[:x.find("/")]
	if '@' in x and x[x.find('@'):] == "@" + server:
		x = x[:x.find("@")]
	return x

def getjid(x):
	"returns a full jid from a display name"
	server = conf['general']['server']
	if '@' not in x:
		x = x + "@" + server
	return x

def has_userflag(jid,flag):
	"return true if the user is a userflag"
	userinfo = conf['userinfo']
	if not userinfo.has_key(getjid(jid)):
		return 0 # False
	return flag in userinfo[getjid(jid)]

def del_userflag(jid,flag):
	"del an flag, return 0 if they didn't have the flag"
	userinfo = conf['userinfo']
	if not has_userflag(jid,flag):
		return 0
	userinfo[getjid(jid)].remove(flag)
	if userinfo[getjid(jid)]==[]:
		del userinfo[getjid(jid)]
	saveconfig()
	return 1

def add_userflag(jid,flag):
	"add an flag to a user, return 0 if they already have that flag"
	userinfo = conf['userinfo']
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
	if conf['general']['debug']:
		print time.strftime("%Y-%m-%d %H:%M:%S"), msg
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
		
def systoall(msg, butnot=[], including=[]):
	sendtoall(conf['general']['sysprompt'] + ' ' + msg, butnot, including)
	
def systoone(who, msg):
	sendtoone(who, conf['general']['sysprompt'] + ' ' + msg)

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
	if not conf['general']['hide_status']:
		return
	if msg:
		systoall(_('%s is %s (%s)') % (who,txt,msg),including=[who])
	else:
		systoall(_('%s is %s') % (who,txt),including=[who])

def boot(jid):
	"Remove a user from the chatroom"
	con.send(jabber.Presence(to=jid, type='unsubscribe'))
	con.send(jabber.Presence(to=jid, type='unsubscribed'))
	if statuses.has_key(getdisplayname(jid)):
		del statuses[getdisplayname(jid)]

def cmd(who,msg):
	userinfo = conf['userinfo']
	if " " in msg:
		cmd,msg=msg.split(" ",1)
	else:
		cmd,msg=msg.strip(),""
	if cmd[:1] in commandchrs:
		cmd=cmd[1:]
	if cmd in ["me"]:
		if msg.strip()=="":
			action=random.choice(conf['emotes'].keys())
			systoone(who, _('Usage: /me <emote>\nSays an emote as you.  eg "/me %(action)s <msg>" shows as "%(nick)s %(emote)s <msg>" to everyone else') % {
				"nick" : getdisplayname(who),
				"action" : action,
				"emote" : conf['emotes'][action]
				})
		else:
			if " " in msg:
				action, msg = msg.split(" ", 1)
			else:
				action, msg = "", msg
			emote = conf['emotes'].get(action, "")
			if emote:
				emote = "_%s_" % emote
			sendtoall(_('<%s> %s %s') % (getdisplayname(who),emote,msg), butnot=[getdisplayname(who)])
	elif cmd in ["help"]:
		systoone(who, _("Commands: \")help\" \"/me\" \")names\" \")quit\" \")msg\""))
		if isadmin(who.getStripped()):
			systoone(who, _('Admin commands: ")die" ")addadmin" ")deladmin" ")listadmins" ")kick" ")ban" ")unban" ")listbans" ")invite"'))
		systoone(who, _('See http://coders.meta.net.nz/~perry/jabber/confbot.php for more details'))
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
		systoone(who, _('Names: %s') % " ".join(names))
	elif cmd in ["quit","leave","exit"]:
		if msg:
			msg = "(%s)" % msg
		systoall(_('Quit: <%s> %s') % (getdisplayname(who),msg))
		boot(who.getStripped())
	elif cmd in ['msg']:
		if not ' ' in msg:
			systoone(who, _('Usage: )msg <nick> <message>'))
		else:
			target,msg = msg.split(' ',1)
			sendtoone(getjid(target), _('*<%s>* %s') % (getdisplayname(who),msg))
			systoone(who,_('>%s> %s') % (getdisplayname(target),msg))
	elif cmd in ['kick','boot'] and isadmin(who.getStripped()):
		boot(getjid(msg.strip()))
		systoall(_('Booted: <%s>') % msg.strip())
	elif cmd in ['ban'] and isadmin(who.getStripped()):
		boot(getjid(msg.strip()))
		addban(getjid(msg.strip()))
		systoall(_('Banned: <%s>') % msg.strip())
	elif cmd in ['unban'] and isadmin(who.getStripped()):
		if delban(getjid(msg.strip())):
			systoone(who, _('Unbanned: <%s>') % getjid(msg.strip()))
		else:
			systoone(who, _('%s is not banned') % getjid(msg.strip()))
	elif cmd in ['listbans'] and isadmin(who.getStripped()):
		systoone(who, _('Banned list: %s') % " ".join([user for user,data in userinfo.items() if isbanned(user)]))
	elif cmd in ['invite'] and isadmin(who.getStripped()):
		con.send(jabber.Presence(to=getjid(msg.strip()), type='subscribe'))
		adduser(getjid(msg.strip()))
		systoone(who, _('Invited <%s>') % getjid(msg.strip()))
	elif cmd in ['addadmin'] and isadmin(who.getStripped()):
		addadmin(msg.strip())
		systoone(who, _('Added <%s>') % getjid(msg.strip()))
		systoone(getjid(msg.strip()), _('<%s> added you as an admin') % getdisplayname(who))
	elif cmd in ['deladmin'] and isadmin(who.getStripped()):
		if has_userflag(getjid(msg.strip()), 'super'):
			systoone(who, _('<%s> is a super admin which can not be deleted.') % getjid(msg.strip()))
		else:
			if deladmin(msg.strip()):
				systoone(who, _('Removed <%s>') % getjid(msg.strip()))
				systoone(getjid(msg.strip()), _('<%s> removed you as an admin') % getdisplayname(who))
			else:
				systoone(who, _('<%s> is not an admin') % getjid(msg.strip()))
	elif cmd in ['listadmins'] and isadmin(who.getStripped()):
		systoone(who,_('Admins: %s') % " ".join([user for user,data in userinfo.items() if isadmin(user)]))
	elif cmd in ['die'] and isadmin(who.getStripped()):
		if msg.strip():
			systoall(_('Admin shutdown by <%s> (%s)') % (who.getStripped(),msg))
		else:
			systoall(_('Admin shutdown by <%s>') % who.getStripped())
		sys.exit(1)
	elif cmd in ['reload'] and isadmin(who.getStripped()):
		readconfig()
		systoone(who, _('Config reloaded'))
	else:
		systoone(who, _('Unknown command %s') % cmd)

def messageCB(con,msg):
	if msg.getError()!=None:
		if statuses.has_key(getdisplayname(msg.getFrom())):
			sendstatus(unicode(msg.getFrom()),_("away"), _("Blocked"))
		boot(msg.getFrom().getStripped())
	elif msg.getBody():
		if len(msg.getBody())>1024:
			systoall(_("%s is being a moron trying to flood the channel") % (getdisplayname(msg.getFrom())))
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
				systoone(msg.getFrom(), _('Warning: You are marked as "busy" in your client,\nyou will not see other people talk,\nset yourself "available" in your client to see their replies.'))
	xmllogf.flush() # just so flushes happen regularly


def presenceCB(con,prs):
	userinfo = conf['userinfo']
	who = unicode(prs.getFrom())
	type = prs.getType()
	# TODO: Try only acking their subscription when they ack ours.
	if type == 'subscribe':
		print "Subscribe from",who,
		if isbanned(prs.getFrom().getStripped()):
			systoone(who, _('You are banned'))
			boot(prs.getFrom().getStripped())
			print "Banned"
		elif conf['general']['private'] and not isuser(prs.getFrom().getStripped()):
			systoone(who, _('This is a private conference bot'))
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
		systoone(who, welcome % {'version':version})
		systoone(who, '''Topic: %(topic)s
%(lastlog)s''' % {
			"topic" : conf['general']['topic'],
			"lastlog" : "\n".join(lastlog),
			})
		sendstatus(who, _('here'), _('joining'))
		if userinfo=={}: # No admins?
			# Add this user as the only admin
			addadmin(who.getStripped())
	elif type == 'unsubscribed':
		boot(prs.getFrom().getStripped())
		systoall(_('<%s> has left') % getdisplayname(who))
	elif type == 'available' or type == None:
		show = prs.getShow()
		if show in [None,'chat','available','online']:
			sendstatus(who, _('here'),prs.getStatus())
		elif show in ['xa']:
			sendstatus(who, _('away'),prs.getStatus())
		elif show in ['away']:
			sendstatus(who, _('away'),prs.getStatus())
		elif show in ['dnd']:
			sendstatus(who, _('away'),prs.getStatus())
		else:
			sendstatus(who, _('away'),show+" [[%s]]" % prs.getStatus())

	elif type == 'unavailable':
		status = prs.getShow()
		sendstatus(who, _('away'),status)
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
		reply.setError('501', _('Feature not implemented'))
		con.send(reply)
	except:
		traceback.print_exc()

def disconnectedCB(con):
	sys.exit(1)

def readoptionorprompt(section, option, description):
	"Read an option from the general section of the config, or prompt for it"
	val = conf[section].get(option)
	if not val:
		print description,
		conf[section][option] = raw_input([option])
	
def readconfig():
	global conf, welcome

	if len(sys.argv)>1:
		conf = ConfigObj(sys.argv[1])
	else:
		conf = ConfigObj("confbot.ini")

	#set default value
	if not conf.has_key('general'):
		conf['general'] = {}
	conf['general'].setdefault('server', 'gmail.com')
	conf['general'].setdefault('resource', 'conference')
	conf['general'].setdefault('private', 0)
	conf['general'].setdefault('hide_status', 0)
	conf['general'].setdefault('debug', 1)
	conf['general'].setdefault('configencoding', 'utf-8')
	conf['general'].setdefault('sysprompt', '***')	#system infomation prompt string
	conf['general'].setdefault('logpath', '')
	conf['general'].setdefault('language', '')
	
	if not conf.has_key('emotes'):
		conf['emotes'] = {}
	conf['emotes'].setdefault('cry', _('cries'))
	conf['emotes'].setdefault('jump', _('jumps'))
	conf['emotes'].setdefault('hop', _('hops'))
	conf['emotes'].setdefault('sigh', _('sighs'))
	conf['emotes'].setdefault('fart', _('farts'))
	conf['emotes'].setdefault('smile', _('smiles'))
	conf['emotes'].setdefault('keeldie', _('keels over and dies'))
	conf['emotes'].setdefault('clap', _('claps'))

	#get real value
	readoptionorprompt('general', "account", _("What is the account name of your bot:"))
	readoptionorprompt('general', "password", _("What is the password of your bot:"))
	readoptionorprompt('general', "topic", _("Write a short description about your bot:"))
	
	#conver int value
	conf['general']['private'] = int(conf['general']['private'])
	conf['general']['hide_status'] = int(conf['general']['hide_status'])
	conf['general']['debug'] = int(conf['general']['debug'])
	
	#encoding convert
	encoding = conf['general']['configencoding']
	conf['general']['sysprompt'] = unicode(conf['general']['sysprompt'], encoding)
	conf['general']['topic'] = unicode(conf['general']['topic'], encoding)
	
	if not conf.has_key('userinfo'):
		conf['userinfo'] ={}
		if os.path.exists('adminlist.txt'):
			adminfile = open("adminlist.txt","r")
			admins=[i.strip() for i in adminfile.readlines()]
			adminfile.close()
			print "Migrating admin list"
			for i in admins:
				conf['userinfo'][i]=["admin"]
		else:
			print _("Input super admin email account:"),
			admin = raw_input()
			conf['userinfo'][admin] = ['admin', 'super']
			
	#deal with welcome message
	if os.path.exists('welcome.txt'):
		welcome = unicode(file('welcome.txt').read(), encoding)
			
def saveconfig():
	"Saves the config to disk"
	#encoding convert
	encoding = conf['general']['configencoding']
	conf['general']['sysprompt'] = conf['general']['sysprompt'].encode('utf-8')
	conf['general']['topic'] = conf['general']['topic'].encode('utf-8')
	conf.write()
	file('welcome.txt', 'w').write(welcome.encode('utf-8'))

def connect():
	debug = conf['general']['debug']
	
	print "Connecting"
	general = conf['general']
	if debug:
		print 'debug is [On]'
		print 'host is [%s]' %general['server']
		print 'account is [%s]' % general['account']
		print 'resource is [%s]' % general['resource']
	con = jabber.Client(host=general['server'],debug=False ,log=xmllogf,
						port=5223, connection=xmlstream.TCP_SSL)
	print "Logging in"
	con.connect()
	con.setMessageHandler(messageCB)
	con.setPresenceHandler(presenceCB)
	con.setIqHandler(iqCB)
	con.setDisconnectHandler(disconnectedCB)
	con.auth(general['account'], general['password'], general['resource'])
	con.requestRoster()
	con.sendInitPresence()
	print "Online!"
	_roster = con.getRoster()
	return con


readconfig()
saveconfig()

#set system default encoding to support unicode
reload(sys)
sys.setdefaultencoding('utf-8')

#logfile process
logf = open(os.path.join(conf['general']['logpath'], time.strftime("%Y%m%d%H%M%S.log")),"w")

general = conf['general']
con = connect()
JID="%s@%s/%s" % (general['account'], general['server'], general['resource'])
last_update=0
last_ping=0
while 1:
	# We announce ourselves to a url, this url then keeps track of all
	# the conference bots that are running, and provides a directory
	# for people to browse.
	if time.time()-last_update>4*60*60 and not general['private']: # every 4 hours
		args={
			'action':'register',
			'account':"%s@%s" % (general['account'], general['server']),
			'users':len(con.getRoster().getJIDs()),
			'last_activity':time.time()-last_activity,
			'version':version,
			'topic':general['topic'],
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
	try:
		if time.time()-last_ping>120: # every 2 minutes
			# Say we're online.
			con.send(jabber.Presence())
		con.process(1)
	except KeyboardInterrupt:
		break
	except SystemExit:
		break
	except:
		traceback.print_exc()
		try:
			time.sleep(1)
			con = connect()
		except KeyboardInterrupt:
			break
		except:
			traceback.print_exc()