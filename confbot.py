#!/usr/bin/env python
# confbot -- a conference bot for google talk.
# Copyright (C) 2005 Perry Lorier (aka Isomer) and Limodou
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
#    Update 2005/09/06
#      * Add 'nochat' flag
#      * Add /chat /nochat /status /version command
#    Update 2005/09/07
#      * Add listemotes command
#      * Add addemote <action> <representation> command
#      * Add setoption <option> value command you can control private, hide_status, debug, topic, sysprompt
#      * Add listoptions
#      * Add delemote <emote> command
#      * Add lang <language> command to switch native lanauge for one user
#      * Add switch multilang functionality on the fly
#      * Add logfileformat option, so you can put one day log into one file
#      * Add listlangs command shows available translation languages, en is default
#    Update 2005/09/08
#      * Add restart command
#      * logfile can be create new file as day past by
#      * Remove listadmins and listbans command, because /names is ok
#      * Add status command, so you can set bot's status
#      * Fix bugs
#    Update 2005/09/09
#      * Change restart to reconnect, it's more clearly
#      * Change some command according to IRC: status->whois, nochat->away
#      * Change away command just like irc, if has a msg, add 'away' flag to user, if no msg, remove 'away' flag
#      * Add mode command to set some option, just like skip system prompt /mode +s On /mode -s Off
#      * Auto send present to online people
#      * Redesign the process of /help command, make cmd_x function docstring in help infomation
#      * Add auto reconnect mechanism as network delay is too long
#############################################################################################

#i18n process
import sys
import socket
import jabber
import xmlstream
import time
import random
import traceback
import urllib
import os.path
import i18n
import locale
import threading

version = '1.9a'
revision = '$Revision$'
commandchrs = '/)'

from configobj import ConfigObj

def getlocale():
	if len(sys.argv)>1:
		conf = ConfigObj(sys.argv[1])
	else:
		conf = ConfigObj("confbot.ini")
	try:
		loc = conf['general']['language']
	except:
		loc = ''
	if not loc:
		loc = locale.getdefaultlocale()[0]
	if loc is None:
		loc = 'en'
	return loc

i18n.install('confbot', 'locale', getlocale())

conf = None	#global config object
userinfo = None
welcome = _("""Welcome to ConferenceBot %(version)s
By Isomer (Perry Lorier) and Limodou
This conference bot is set up to allow groups of people to chat.
")help" to list commands, ")quit" to quit
")list en" for English, and ")list zh_CN" for Chinese""")

xmllogf = open("xmpp.log","w")
last_activity=time.time()
#xmllogf = sys.stderr
lastlog = []

class ADMIN_COMMAND(Exception):pass
class MSG_COMMAND(Exception):pass
class NOMAN_COMMAND(Exception):pass
class RECONNECT_COMMAND(Exception):pass

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
	x = getdisplayname(x)
	if '@' not in x:
		x = x + "@" + server
	return x

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
#	if userinfo[getjid(jid)]==[]:
#		del userinfo[getjid(jid)]
	saveconfig()
	return 1

def set_userflag(jid,flag):
	"set an flag, remove all existed flag"
	jid = getjid(jid)
	if flag != 'user':
		userinfo[jid] = ['user', flag]
	else:
		userinfo[jid] = ['user']
	saveconfig()
	return 1

def del_langflag(jid):
	flags = userinfo[jid]
	for i in flags[:]:
		if i.startswith('*'):
			del_userflag(jid, i)
			break
	saveconfig()

def add_langflag(jid, flag):
	del_langflag(jid)
	add_userflag(jid, flag)
	saveconfig()

def add_userflag(jid,flag):
	"add an flag to a user, return 0 if they already have that flag"
	if has_userflag(jid,flag):
		return 0
	if not userinfo.has_key(getjid(jid)):
		userinfo[getjid(jid)]=[flag]
	else:
		userinfo[getjid(jid)].append(flag)
	saveconfig()
	
def get_userlang(jid):
	lang = None
	for u, flags in userinfo.items():
		if u == getjid(jid):
			for f in flags:
				if f.startswith('*'):
					lang = f[1:]
					break
			break
	return lang

def issuper(jid):	return has_userflag(jid,"super")
def isadmin(jid):	return has_userflag(jid,"admin") or has_userflag(jid,"super")
def deladmin(jid):	return del_userflag(jid,"admin")
def addadmin(jid):	return add_userflag(jid,"admin")
def isbanned(jid):	return has_userflag(jid,"banned")
def delban(jid):	return del_userflag(jid,"banned")
def addban(jid):	return set_userflag(jid,"banned")

def isuser(jid):	return has_userflag(jid,"user")
def deluser(jid):	return del_userflag(jid,"user")
def adduser(jid):	return add_userflag(jid,"user")

def sendtoone(who, msg):
	if i18n.isobj(msg):
		msg.setlang(get_userlang(getjid(who)))
		msg = msg.getvalue()

	m = jabber.Message(getjid(who), msg)
	m.setFrom(JID)
	m.setType('chat')
	if conf['general']['debug'] > 1:
		print '...Begin....................', who
	con.send(m)
#	time.sleep(.1)

def sendtoall(msg,butnot=[],including=[]):
	global lastlog
	r = con.getRoster()
	print >>logf,time.strftime("%Y-%m-%d %H:%M:%S"), msg.encode("utf-8")
	logf.flush()
	if conf['general']['debug']:
		try:
			print time.strftime("%Y-%m-%d %H:%M:%S"), msg.encode(locale.getdefaultlocale()[1])
		except:
			print time.strftime("%Y-%m-%d %H:%M:%S"), msg.encode('utf-8')
	for i in r.getJIDs():
		if getdisplayname(i) in butnot:
			continue
		state=r.isOnline(i)
		if has_userflag(getdisplayname(i), 'away'): #away is represent user don't want to chat
			continue
		if r.isOnline(i) and r.getShow(i) in ['available','chat','online',None]:
			sendtoone(i, msg)
	if not msg.startswith(conf['general']['sysprompt']):
		lastlog.append(msg)
	if len(lastlog)>5:
		lastlog=lastlog[1:]
		
def sendtoadmin(msg,butnot=[],including=[]):
	global lastlog
	r = con.getRoster()
	print >>logf,time.strftime("%Y-%m-%d %H:%M:%S"), msg.encode("utf-8")
	logf.flush()
	if conf['general']['debug']:
		try:
			print time.strftime("%Y-%m-%d %H:%M:%S"), msg.encode(locale.getdefaultlocale()[1])
		except:
			print time.strftime("%Y-%m-%d %H:%M:%S"), msg.encode('utf-8')
	for i in r.getJIDs():
		if not isadmin(i): continue
		if getdisplayname(i) in butnot:
			continue
		state=r.getShow(unicode(i))
		if has_userflag(getdisplayname(i), 'away'): #away is represent user don't want to chat
			continue
		if state in ['available','chat','online',None] or getdisplayname(i) in including :
			sendtoone(i,msg)
			time.sleep(.2)
	if not msg.startswith(conf['general']['sysprompt']):
		lastlog.append(msg)
	if len(lastlog)>5:
		lastlog=lastlog[1:]

def systoall(msg, butnot=[], including=[]):
	user = butnot[:]
	for i in userinfo.keys():
		if has_userflag(i, 's'):
			user.append(i)
	sendtoall(conf['general']['sysprompt'] + ' ' + msg, user, including)
	
def systoone(who, msg):
#	if not has_userflag(getjid(who), 's'):
	sendtoone(who, conf['general']['sysprompt'] + ' ' + msg)
	
def systoadmin(msg, butnot=[], including=[]):
	sendtoadmin(conf['general']['sysprompt'] + ' ' + msg, butnot, including)

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
		systoall(_('%s is %s (%s)').para(who,txt,msg),including=[who])
	else:
		systoall(_('%s is %s').para(who,txt),including=[who])

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
	cmd = cmd.lower()
	func = None
	try:
		if commands.has_key(cmd):
			func = commands[cmd]
			func(who, msg)
		elif acommands.has_key(cmd):
			func = acommands[cmd]
			func(who, msg)
		else:
			systoone(who, _('Unknown command "%s".').para(cmd))
	except ADMIN_COMMAND:
		systoone(who, _('This is admin command, you have no permision to use.'))
	except MSG_COMMAND:
		f = _
		systoone(who, f(func.__doc__))
	except NOMAN_COMMAND:
		systoone(who, _('There is no this person'))

def cmd_me(who, msg):
	'"/me <emote> [<msg>]" Says an emote as you'
	if msg.strip()=="":
		action=random.choice(conf['emotes'].keys())
		systoone(who, _('Usage: /me <emote>\nSays an emote as you.  eg "/me %(action)s <msg>" shows as "%(nick)s %(emote)s <msg>" to everyone else').para({
			"nick" : getdisplayname(who),
			"action" : action,
			"emote" : conf['emotes'][action]
			}))
	else:
		if " " in msg:
			action, msg = msg.split(" ", 1)
		else:
			action, msg = msg, " "
		emote = conf['emotes'].get(action, "")
		if emote:
			emote = "_%s_" % emote
		sendtoall(_('<%s> %s %s').para(getdisplayname(who),emote,msg), butnot=[getdisplayname(who)])
		systoone(who, _('You %s %s').para(emote, msg))
	
def cmd_help(who, msg):
	'"/help" Show this help message'
	jid = who.getStripped()
	f = _
	systoone(who, _('Commands: \n%s').para(' /' + ' /'.join(["%-20s%s\n" % (x, unicode(f(y.__doc__, get_userlang(jid))) or "") for x, y in commands.items()])))
	if isadmin(who.getStripped()):
		systoone(who, _('Admin commands: \n%s').para(' /' + ' /'.join(["%-20s%s\n" % (x, unicode(f(y.__doc__, get_userlang(jid))) or "") for x, y in acommands.items()])))
	systoone(who, _('See http://coders.meta.net.nz/~perry/jabber/confbot.php for more details.\nAlso see http://www.donews.net/limodou for Chinese version.'))

def cmd_names(who, msg):
	'"/names" List all the people in the room'
	r = con.getRoster()
	names=[]
	for i in r.getJIDs():
		state=r.getOnline(unicode(i))
		name=getdisplayname(i)
		if isadmin(i.getStripped()):
			name="@%s" % name
		if has_userflag(i.getStripped(), 'away'):
			name="-%s" % name
		if has_userflag(i.getStripped(), 'banned'):
			name="#%s" % name
		if state in ['available','chat','online',None]:
			names.insert(0,name)
		else:
			names.append('(%s)' % name)
	systoone(who, _('Names: total (%d)\n%s').para(len(names), " ".join(names)))

def cmd_leave(who, msg):
	'"/leave" The same as /quit'
	cmd_quit(who, msg)
	
def cmd_exit(who, msg):
	'"/leave" The same as /quit'
	cmd_quit(who, msg)

def cmd_quit(who, msg):
	'"/quit" Quit this room for ever'
	if msg:
		msg = "(%s)" % msg
	systoall(_('Quit: <%s> %s').para(getdisplayname(who),msg))
	if not issuper(who):
		boot(who.getStripped())

def cmd_msg(who, msg):
	'"/msg nick message" Send a private message to someone'
	if not ' ' in msg:
		systoone(who, _('Usage: )msg nick message'))
	else:
		if has_userflag(who.getStripped(), 'away'):
			systoone(who, _('Warning: Because you set "away" flag, so you can not receive and send any message from this bot, until you reset using "/away" command')) 
			return
		target,msg = msg.split(' ',1)
		if has_userflag(target, 'away'):
			systoone(who, _('<%s> has set himself in "away" mode, so you could not send him a message.').para(getjid(target))) 
			return
		sendtoone(getjid(target), _('*<%s>* %s').para(getdisplayname(who), msg))
		systoone(who, _('>%s> %s').para(getdisplayname(target), msg))

def acmd_boot(who, msg):
	'"/boot" The same as /kick'
	acmd_kick(who, msg)
	
def acmd_kick(who, msg):
	'"/kick nick" Kick someone out of this room'
	if isadmin(who.getStripped()):
		jid = getjid(msg.strip())
		if userinfo.has_key(jid):
			boot(jid)
			del userinfo[jid]
			saveconfig()
			systoall(_('Booted: <%s>').para(msg.strip()))
	else:
		raise ADMIN_COMMAND

def acmd_ban(who, msg):
	'"/ban nick" Forbid someone rejoin this room'
	msg = msg.strip()
	if isadmin(who.getStripped()):
		if msg:
			jid = getjid(msg)
			if userinfo.has_key(jid):
				boot(jid)
				addban(msg)
				systoall(_('Banned: <%s>').para(msg))
			else:
				raise NOMAN_COMMAND
		else:
			raise MSG_COMMAND
	else:
		raise ADMIN_COMMAND

def acmd_unban(who, msg):
	'"/unban nick" Permit someone rejoin this room'
	msg = msg.strip()
	jid = getjid(msg)
	if isadmin(who.getStripped()):
		if msg:
			if delban(jid):
				systoone(who, _('Unbanned: <%s>').para(jid))
			else:
				systoone(who, _('%s is not banned').para(jid))
		else:
			raise MSG_COMMAND
	else:
		raise ADMIN_COMMAND

def acmd_invite(who, msg):
	'"/invite nick" Invite someone to join this room'
	msg = msg.strip()
	jid = getjid(msg)
	if isadmin(who.getStripped()):
		if msg:
			con.send(jabber.Presence(to=jid, type='subscribe'))
			adduser(jid)
			systoone(who, _('Invited <%s>').para(jid))
		else:
			raise MSG_COMMAND
	else:
		raise ADMIN_COMMAND
	
def acmd_addadmin(who, msg):
	'"/addadmin nick" Set someone as administrator'
	msg = msg.strip()
	if isadmin(who.getStripped()):
		if msg:
			if who.getStripped() != msg:
				addadmin(msg)
				systoone(who, _('Added <%s>').para(getjid(msg)))
				systoone(getjid(msg), _('<%s> added you as an admin').para(getdisplayname(who)))
			else:
				systoone(who, _('You are an admin already.'))
		else:
			raise MSG_COMMAND
	else:
		raise ADMIN_COMMAND
		
def acmd_deladmin(who, msg):
	'"/deladmin nick" Remove admin right from someone'
	msg = msg.strip()
	if isadmin(who.getStripped()):
		if msg:
			if issuper(msg, 'super'):
				systoone(who, _('<%s> is a super admin which can not be deleted.').para(getjid(msg)))
			else:
				if deladmin(msg):
					systoone(who, _('Removed <%s>').para(getjid(msg)))
					systoone(getjid(msg), _('<%s> removed you as an admin').para(getdisplayname(who)))
				else:
					systoone(who, _('<%s> is not an admin').para(getjid(msg)))
		else:
			raise MSG_COMMAND
	else:
		raise ADMIN_COMMAND
		
def acmd_die(who, msg):
	'"/die [message]" Close the room'
	msg = msg.strip()
	if isadmin(who.getStripped()):
		if msg:
			systoall(_('Room shutdown by <%s> (%s)').para(who.getStripped(),msg))
		else:
			systoall(_('Room shutdown by <%s>').para(who.getStripped()))
		sys.exit(1)
	else:
		raise ADMIN_COMMAND
	
def acmd_reload(who, msg):
	'"/reload" Reload the config'
	if isadmin(who.getStripped()):
		readconfig()
		systoone(who, _('Config reloaded'))
	else:
		raise ADMIN_COMMAND

def cmd_away(who, msg):
	'"/away [message]" Set "away"(need message) or "chat"(no message) flag of someone' 
	msg = msg.strip()
	if msg:
		add_userflag(who.getStripped(), 'away')
		systoall(_('%s is temporarily away. (%s)').para(who.getStripped(), msg), [who])
		systoone(who, _('Warning: Because you set "away" flag, so you can not receive and send any message from this bot, until you reset using "/chat" command')) 
	else:
		del_userflag(who.getStripped(), 'away')
		systoall(_('%s is actively interested in chatting.').para(who.getStripped()), [who])
		systoone(who, _('You can begin to chat now.'))

def cmd_whois(who, msg):
	'"/whois [nick]" View someone\'s status'
	msg = msg.strip()
	jid = getjid(msg)
	if msg and isadmin(who.getStripped()):
		if userinfo.has_key(jid):
			status = userinfo[jid]
			systoone(who, _('Info: %s').para(" ".join(status)))
		else:
			raise NOMAN_COMMAND
	else:
		status = userinfo[who.getStripped()]
		systoone(who, _('Info: %s').para(" ".join(status)))
	
def cmd_version(who, msg):
	'"/version" Show version of this bot'
	systoone(who, _('Version: %s (%s)\nSee http://coders.meta.net.nz/~perry/jabber/confbot.php for more details.\nAlso see http://www.donews.net/limodou for Chinese version.').para(version, revision))

def cmd_listemotes(who, msg):
	'"/listemotes" List all emote string'
	emotes = conf['emotes']
	txt = []
	for key, value in emotes.items():
		txt.append('%s : %s' % (key, value))
	systoone(who, _('Emotes : \n%s').para('\n'.join(txt)))
	
def acmd_addemote(who, msg):
	'"/addemote action emote" Add emote string'
	msg = msg.strip()
	if isadmin(who.getStripped()):
		if not msg or ' ' not in msg:
			raise MSG_COMMAND
		else:
			action, msg = msg.split(' ', 1)
			conf['emotes'][action] = msg
			saveconfig()
			systoone(who, _('Success'))
	else:
		raise ADMIN_COMMAND

def acmd_delemote(who, msg):
	'"/delemote action" Del emote string'
	msg = msg.strip()
	if isadmin(who.getStripped()):
		if msg:
			if conf['emotes'].has_key(msg):
				emotes = conf['emotes']
				del emotes[msg]
				saveconfig()
				systoone(who, _('Success'))
			else:
				systoone(who, _('Emote [%s] is not exist.').para(msg))
		else:
			raise MSG_COMMAND
	else:
		raise ADMIN_COMMAND

options = ['language', 'private', 'hide_status', 'debug', 'topic', 'sysprompt', 'logfileformat', 'status']
def acmd_setoption(who, msg):
	'"/setoption option value" Set an option\'s value'
	msg = msg.strip()
	if isadmin(who.getStripped()):
		if not msg or ' ' not in msg:
			raise MSG_COMMAND
		else:
			option, msg = msg.split(' ', 1)
			if option in options:
				if option in ('private', 'hide_status'):
					if msg.lower() in ("1", "yes", "on", "true"):
						value = 1
					else:
						value = 0
				if option == 'debug':
					try:
						value = int(msg)
					except:
						value = 0
				else:
					value = msg
				conf['general'][option] = value 
				saveconfig()
				systoone(who, _('Success'))
			else:
				systoone(who, _('Option [%s] may not exist or can not be set.').para(option))
	else:
		raise ADMIN_COMMAND

def acmd_listoptions(who, msg):
	'"/listoptions" List all options that can be changed'
	msg = msg.strip()
	if isadmin(who.getStripped()):
		txt = []
		for option in options:
			if option in ('private', 'hide_status'):
				if conf['general'][option]:
					value = 'On'
				else:
					value = 'Off'
			else:
				value = conf['general'][option]
			txt.append("%s : %s" % (option, value))
		systoone(who, _('Options: \n%s').para('\n'.join(txt)))
	else:
		raise ADMIN_COMMAND
	
def cmd_lang(who, msg):
	'"/lang [language]" Set language to "language" or reset to default'
	msg = msg.strip()
	if msg:
		add_langflag(who.getStripped(), '*%s' % msg)
		systoone(who, _('Your language has been set as "%s".').para(msg))
	else:
		del_langflag(who.getStripped())
		systoone(who, _('Your language has been set as default.'))
		
def cmd_listlangs(who, msg):
	'"/listlangs" List all support language'
	systoone(who, _('Available languages: %s').para(' '.join(i18n.listlang())))
	
def acmd_reconnect(who, msg):
	'"/reconnect" Reconnect the server'
	if isadmin(who.getStripped()):
		systoadmin(_('Reconnecting ...'))
		raise RECONNECT_COMMAND
	else:
		raise ADMIN_COMMAND

def cmd_status(who, msg):
	'"/status [message]" Set or see the bot\'s status'
	msg = msg.strip()
	if isadmin(who.getStripped()):
		if msg:
			conf['general']['status'] = msg
			saveconfig()
			sendpresence(msg)
			systoone(who, _('Status has been set as: %s').para(msg))
		else:
			systoone(who, _('Status is: %s').para(conf['general']['status']))
	else:
		raise ADMIN_COMMAND
	
def cmd_mode(who, msg):
	'"/mode option" Set or remove flag to someone. For example: "+s" filter system message, "-s" receive system message'
	msg = msg.strip()
	if msg:
		setflag = True
		if msg[0] == '+':	#set
			setflag = True
			msg = msg[1:]
		elif msg[0] == '-':
			setflag = False
			msg = msg[1:]
		if msg == 's':
			if setflag:
				add_userflag(who, 's')	#s instead of skip system message
				systoone(who, _('The proceed public system messages will be skipped. Until you run /mode -s command'))
			else:
				del_userflag(who, 's')
				systoone(who, _('You can receive public system messages now.'))
			return
	systoone(who, _('Usage: /mode [+]s'))

def sendpresence(msg):
	p = jabber.Presence()
	p.setStatus(msg)
	con.send(p)
	
def messageCB(con,msg):
	global ontesting
	whoid = getjid(msg.getFrom())
	if conf['general']['debug'] > 2:
		try:
			print '>>>', time.strftime('%Y-%m-%d %H:%M:%S'), '[MESSAGE]', unicode(msg).encode(locale.getdefaultlocale()[1])
		except:
			print '>>>', time.strftime('%Y-%m-%d %H:%M:%S'), '[MESSAGE]', unicode(msg).encode('utf-8')
	if msg.getError()!=None:
		if conf['general']['debug'] > 2:
			try:
				print '>>> [ERROR]', unicode(msg).encode(locale.getdefaultlocale()[1])
			except:
				print '>>> [ERROR]', unicode(msg).encode('utf-8')
#		if statuses.has_key(getdisplayname(msg.getFrom())):
#			sendstatus(unicode(msg.getFrom()),_("away"), _("Blocked"))
#		boot(msg.getFrom().getStripped())
	elif msg.getBody():
		#check quality
		if msg.getFrom().getStripped() == getjid(JID):
			body = msg.getBody()
			if body and body[0] == 'Q':
				ontesting = False
				t = int(body[1:].split(':', 1)[0])
				t1 = int(time.time())
				if t1 - t > reconnectime:
					if conf['general']['debug'] > 1:
						print '>>>', time.strftime('%Y-%m-%d %H:%M:%S'), 'RECONNECT... network delay it too long: %d\'s' % (t1-t)
					raise RECONNECT_COMMAND
			xmllogf.flush()
			return
		userjid[whoid] = unicode(msg.getFrom())
		if len(msg.getBody())>1024:
			systoall(_("%s is being a moron trying to flood the channel").para(getdisplayname(msg.getFrom())))
		elif msg.getBody()[:1] in commandchrs:
			if conf['general']['debug'] > 1:
				print '......CMD......... %s [%s]' % (msg.getFrom(), msg.getBody())
			cmd(msg.getFrom(),msg.getBody())
		else:
			#check away
			if has_userflag(msg.getFrom().getStripped(), 'away'):
				systoone(msg.getFrom().getStripped(), _('Warning: Because you set "away" flag, so you can not receive and send any message from this bot, until you reset using "/away" command'))
				xmllogf.flush()
				return
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
	if conf['general']['debug'] > 3:
		print '>>>', time.strftime('%Y-%m-%d %H:%M:%S'), '[PRESENCE]', prs
	userinfo = conf['userinfo']
	who = unicode(prs.getFrom())
	whoid = getjid(who)
	type = prs.getType()
	# TODO: Try only acking their subscription when they ack ours.
	if type == 'subscribe':
		print ">>> Subscribe from",whoid,
		if isbanned(prs.getFrom().getStripped()):
			print "Banned"
			systoone(who, _('You are banned'))
			boot(prs.getFrom().getStripped())
		elif conf['general']['private'] and not isuser(prs.getFrom().getStripped()):
			print "Uninvited"
			systoone(who, _('This is a private conference bot'))
			boot(prs.getFrom().getStripped())
		else:
			print "Accepted"
			con.send(jabber.Presence(to=who, type='subscribed'))
			con.send(jabber.Presence(to=who, type='subscribe'))
			systoall(_('<%s> joins this room.').para(getdisplayname(who)), [who])
			userjid[whoid] = who
	elif type == 'unsubscribe':
		if userjid.has_key(whoid):
			del userjid[whoid]
		boot(prs.getFrom().getStripped())
		print ">>> Unsubscribe from",who
	elif type == 'subscribed':
		if i18n.isobj(welcome):
			wel = welcome.getvalue()
		else:
			wel = welcome
		systoone(who, wel % {'version':version})
		systoone(who, _('''Topic: %(topic)s
%(lastlog)s''').para({
			"topic" : conf['general']['topic'],
			"lastlog" : "\n".join(lastlog),
			})  + '\n---------------------------')
		sendstatus(who, _('here'), _('joining'))
		userjid[whoid] = who
	elif type == 'unsubscribed':
		if userjid.has_key(whoid):
			del userjid[whoid]
		boot(prs.getFrom().getStripped())
		systoall(_('<%s> has left').para(getdisplayname(who)))
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
		userjid[whoid] = who
	elif type == 'unavailable':
		status = prs.getShow()
		sendstatus(who, _('away'),status)
	else:
		if conf['general']['debug'] > 3:
			print ">>> Unknown presence:",who,type


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
	#sys.exit(1)
	raise RECONNECT_COMMAND

def readoptionorprompt(section, option, description):
	"Read an option from the general section of the config, or prompt for it"
	val = conf[section].get(option)
	if not val:
		print description,
		conf[section][option] = raw_input()
	
def readconfig():
	global conf, welcome, userinfo

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
	conf['general'].setdefault('logfileformat', '%Y%m%d')
	conf['general'].setdefault('status', _('Ready'))
	
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
	conf['general']['sysprompt'] = i18n.Unicode(conf['general']['sysprompt'], encoding)
	conf['general']['topic'] = i18n.Unicode(conf['general']['topic'], encoding)
	conf['general']['status'] = i18n.Unicode(conf['general']['status'], encoding)
	for key, value in conf['emotes'].items():
		conf['emotes'][key] = i18n.Unicode(value, encoding)
	
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
			conf['userinfo'][admin] = ['user', 'super']
			
	#deal with welcome message
	if os.path.exists('welcome.txt'):
		welcome = unicode(file('welcome.txt').read(), encoding)
		
	userinfo = conf['userinfo']
			
def saveconfig():
	"Saves the config to disk"
	try:
		#encoding convert
		encoding = conf['general']['configencoding']
		conf['general']['sysprompt'] = conf['general']['sysprompt'].encode(encoding)
		conf['general']['topic'] = conf['general']['topic'].encode(encoding)
		conf['general']['status'] = conf['general']['status'].encode(encoding)
		for key, value in conf['emotes'].items():
			conf['emotes'][key] = value.encode(encoding)
			
		conf.write()
		file('welcome.txt', 'w').write(welcome.encode(encoding))
	except:
		traceback.print_exc()
		
def connect():
	global con
	debug = conf['general']['debug']
	
	print ">>> Connecting"
	general = conf['general']
	if debug:
		print '>>> debug is [%d]' % general['debug']
		print '>>> host is [%s]' %general['server']
		print '>>> account is [%s]' % general['account']
		print '>>> resource is [%s]' % general['resource']
	con = jabber.Client(host=general['server'],debug=False ,log=xmllogf,
						port=5223, connection=xmlstream.TCP_SSL)
	print ">>> Logging in"
	con.connect()
	con.setMessageHandler(messageCB)
	con.setPresenceHandler(presenceCB)
	con.setIqHandler(iqCB)
	con.setDisconnectHandler(disconnectedCB)
	con.auth(general['account'], general['password'], general['resource'])
	con.requestRoster()
	con.sendInitPresence()
	r = con.getRoster()

#	for i in userinfo.keys()[:]:
#		if not i in r.getJIDs() and not issuper(i):
#			del userinfo[i]
	for i in r.getJIDs():
		if not userinfo.has_key(i):
			adduser(getdisplayname(i))
			
	saveconfig()
	sendpresence(conf['general']['status'])
#	systoall(_('Channel is started.'))
	print ">>> Online!"

def register_site():
	global last_update, running
	
	running = True
	
	general = conf['general']
	print '>>> Registing site'
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
		print ">>> Updated directory site"
	except:
		print ">>> Can't reach the directory site"
		traceback.print_exc()
	last_update = time.time()
	running = False
	
readconfig()
saveconfig()

#set system default encoding to support unicode
reload(sys)
sys.setdefaultencoding('utf-8')

#make command list
commands = {}
acommands = {}
import types
for i, func in globals().items():
	if isinstance(func, types.FunctionType):
		if i.startswith('cmd_'):
			commands[i.lower()[4:]] = func
		elif i.startswith('acmd_'):
			acommands[i.lower()[5:]] = func

general = conf['general']

#logfile process
logf = file(os.path.join(general['logpath'], time.strftime(general['logfileformat']) + '.log'), "a+")

con = None
JID="%s@%s/%s" % (general['account'], general['server'], general['resource'])
last_update=0
last_ping=0
last_testing=0
userjid = {}	#saving real jid just like "xxx@gmail.com/gtalkxxxxx"
reconnectime = 30	#network delay exceed this time, so the bot need to reconnect

ontesting = False

running = False
while 1:
	try:
		#create new log file as next day
		general = conf['general']
		logfile = os.path.join(general['logpath'], time.strftime(general['logfileformat']) + '.log')
		if not os.path.exists(logfile):
			logf = file(logfile, "a+")
			
		if not con:
			connect()
		# We announce ourselves to a url, this url then keeps track of all
		# the conference bots that are running, and provides a directory
		# for people to browse.
		if time.time()-last_update>4*60*60 and not general['private']: # every 4 hours
			if not running:
				t = threading.Thread(target=register_site)
				t.setDaemon(True)
				t.start()
		# Send some kind of dummy message every few minutes to make sure that
		# the connection is still up, and to tell google talk we're still
		# here.
		if time.time()-last_ping>120: # every 2 minutes
			# Say we're online.
			p = jabber.Presence()
			p.setFrom(JID)
			con.send(p)
			last_ping = time.time()

		if time.time()-last_testing>60: # every 40 seconds
			#test quality
			if ontesting:	#mean that callback message doesn't be processed, so reconnect again
				print '>>>', time.strftime('%Y-%m-%d %H:%M:%S'), 'RECONNECT... network delay it too long: %d\'s' % (time.time()-last_testing)
				raise RECONNECT_COMMAND
			else:
				ontesting = True
				m = jabber.Message(to=JID, body='Q' + str(int(time.time())) + ':' + time.strftime('%Y-%m-%d %H:%M:%S'))
				con.send(m)
				if conf['general']['debug'] > 1:
					print '>>> Quality testing...', time.strftime('%Y-%m-%d %H:%M:%S')
				last_testing = time.time()

		con.process(1)
	except KeyboardInterrupt:
		break
	except SystemExit:
		break
	except RECONNECT_COMMAND:
		con = None
		ontesting = False
		last_testing = 0
		last_ping = 0
	except:
		traceback.print_exc()
		time.sleep(1)
		con = None
