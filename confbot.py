#!/usr/bin/env python
# confbot -- a conference bot for google talk.
# Copyright (C) 2005 Perry Lorier (aka Isomer) and Limodou
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
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
##############################################################################

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
import re

commandchrs = '/)'

from dict4ini import DictIni

def getlocale():
	uset = DictIni("usettings.ini")
	games = DictIni("Games.ini")
	nick = DictIni("nicklist.ini")
	if len(sys.argv)>1:
		conf = DictIni(sys.argv[1])
	else:
		conf = DictIni("config.ini")
	try:
		loc = conf.general['language']
	except:
		loc = ''
	if not loc:
		loc = locale.getdefaultlocale()[0]
	if loc is None:
		loc = 'en'
	return loc

i18n.install('confbot', 'locale', getlocale())

statcheck = 0

conf = None	#global config object
userinfo = None
nick = None
games = None
qu = an = ra = None
welcome = _("""Welcome to ConferenceBot %(version)s
By Isomer (Perry Lorier) and Limodou
This conference bot is set up to allow groups of people to chat.
")help" to list commands, ")quit" to quit
")lang en" for English, and ")lang zh_CN" for Chinese""")

xmllogf = open("xmpp.log","w")
last_activity=time.time()
#xmllogf = sys.stderr
lastlog = []

class ADMIN_COMMAND(Exception):pass
class TOOLOW_COMMAND(Exception):pass
class MSG_COMMAND(Exception):pass
class CUSS_COMMAND(Exception):pass
class NOMAN_COMMAND(Exception):pass
class RECONNECT_COMMAND(Exception):pass


#==================================================
#=         String Tools                           =
#==================================================
def getdisplayname(x):
	"Converts a user@domain/resource to a displayable nick"
	server = conf.general['server']
	x=unicode(x)
	if '/' in x:
		x = x[:x.find("/")]
	if hasnick(x):
		x = nick.nickname[x]
		x = x.capitalize()
		if issuper(getjid(x)):
			x = '_'+ x +'_'
	if '%' in x and '@msn' in x[x.find('%'):]:
		x = x[:x.find('%')]
	if '@' in x and x[x.find('@'):] == "@" + server:
		x = x[:x.find("@")]
	return x

def getcleanname(x):
	"Converts a user@domain/resource to simply a user name."
	server = conf.general['server']
	x=unicode(x)
	if '/' in x:
		x = x[:x.find("/")]
	if '@' in x and x[x.find('@'):] == "@" + server:
		x = x[:x.find("@")]
	return x

def getjid(x):
	"returns a full jid from a display name"
	server = conf.general['server']
	if x in nick.nickreg.keys():
		x = nick.nickreg.get(x)
		return x
	if x in nick.tempnick.keys():
		x = nick.tempnick.get(x)
		return x
	else:
		x = getcleanname(x)
		if '@' not in x:
			x = x + "@" + server
		return x

def cuss_list():
	"Returns a formated Regex"
	readconfig()
	#print conf.general.get("wordfilter")
	j = convert_seq(conf.general.get("wordfilter"), y = 1)
	#print j
	j = j.strip()
	#print j
	j = re.sub('\s','|',j)
	#print j
	j = '(?i)(' + j + ')+'
	return j

def find_cuss(msg):
	if re.search(wordfilter, msg):
		return 1
	return 0
	
def convert_seq(seq, y = None):
#======================
#= y = 1 sets the string up for the langauge filter.
#= y = 2 sets the string up to be listed in /wordfilter.
#= 3 = 3 sets the string up to check all cmds.
	j = None
	for i in seq:
		k = i
		if y == 1:
			k = re.sub('\[*\B\W*\]*','\s*',k)
			k = re.sub('\[(([^\]])\\\s\*([^\]]))+\]','\s*[\g<2>\g<3>]\s*',k)
			k = re.sub('\*+','*\s*',k)
			k = re.sub('u""','',k)		
		elif y == 2:
			k = re.sub('\Z\W*','\n',k)
		if j:			
			j = j + ' ' + k
		else:
			j = k
		#print j
	return j
		
#==================================================
#=         Flag Tools                             =
#==================================================
def has_flag(key,flag):
	if not conf['general'].has_key(key):
		return 0 # False
	saveall()
	return flag in conf['general'][key]
	
def add_flag(key,flag):
	"add a flag to a key, return 0 if it already has that flag"
	if has_flag(key,flag):
			return 0
	if not conf['general'].has_key(key):
		conf['general'][key]=[flag]
	else:
		conf['general'][key].append(flag)
	saveall()
		
def del_flag(key,flag):
	"del a flag, return 0 if the key doesn't have the flag"
	if not has_flag(key,flag):
		return 0
	conf['general'][key].remove(flag)
	if conf['general'][key]==[]:
		del conf['general'][key]
	saveall()
	return 1

	
#===================================
#=         User Flag Tools         =
#===================================
def has_userflag(jid,flag):
	"return true if the user is a userflag"
	if not userinfo.has_key(getjid(jid)):
		return 0 # False
	return flag in userinfo[getjid(jid)]

def add_userflag(jid,flag):
	"add an flag to a user, return 0 if they already have that flag"
	if has_userflag(jid,flag):
		return 0
	if not userinfo.has_key(getjid(jid)):
		userinfo[getjid(jid)]=[flag]
	else:
		userinfo[getjid(jid)].append(flag)
	saveconfig()
	
def del_userflag(jid,flag):
	"del an flag, return 0 if they didn't have the flag"
	if not has_userflag(jid,flag):
		return 0
	userinfo[getjid(jid)].remove(flag)
	if userinfo[getjid(jid)]==[]:
		del userinfo[getjid(jid)]
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

	
#===================================
#=         Lang Flag Tools         =
#===================================
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
	
def add_langflag(jid,flag):
	del_langflag(jid)
	add_userflag(jid, flag)
	saveconfig()
	
def del_langflag(jid):
	flags = userinfo[jid]
	for i in flags[:]:
		if i.startswith('*'):
			del_userflag(jid, i)
			break
	saveconfig()
	

#==================================================
#=         Misc Tools                             =
#==================================================
def get_svn_version():
	if os.path.getsize(".svn/entries") != 0 and os.path.isdir(".svn"):
		f = file(".svn/entries")
		i = 0
		while i < 13:
			revision = f.readline()
			i = i + 1
		p = re.search('(\d+)', revision)
		conf.general['revision'] = int(p.group(1))
		saveconfig()
		return conf.general['revision']
	elif not conf.general['revision']:
		return conf.general['revision']
	else:
		return 'Unknown'

def check_status(jid):
	if con.getRoster().getShow(jid) not in ['available','chat','online',None]:
		return 1
	return 0
	
def check_nick(jid):
	if nick['nickname'].has_key(jid):
		return 1
	return 0

def issuper(jid):	return has_userflag(jid,"super")
def issadmin(jid):	return has_userflag(jid,"admin") or has_userflag(jid,"super")
def isadmin(jid):  	return has_userflag(jid,"admin")
def deladmin(jid):	return del_userflag(jid,"admin")
def addadmin(jid):	return add_userflag(jid,"admin")
def isbanned(jid):	return has_userflag(jid,"banned")
def delban(jid):	return del_userflag(jid,"banned")
def addban(jid):	return set_userflag(jid,"banned")
def ismuted(jid):  	return has_userflag(jid,"muted")
def delmute(jid):	return del_userflag(jid,"muted")
def addmute(jid):	return add_userflag(jid,"muted")
def isbusy(jid):	return check_status(jid)
def iscamo(jid):	return has_userflag(jid, "camo")

def addfilter(flag):	return add_flag('wordfilter', flag)
def getcuss(msg):	return cuss_list(msg)
def iscuss(msg):	return find_cuss(msg)
def hasnick(jid):	return check_nick(jid)

def isuser(jid):	return has_userflag(jid,"user")
def deluser(jid):	return del_userflag(jid,"user")
def adduser(jid):	return add_userflag(jid,"user")


#==================================================
#=         Message Functions                      =
#==================================================
def sendtoone(who, msg):
	if i18n.isobj(msg):
		msg.setlang(get_userlang(getjid(who)))
		msg = msg.getvalue()

	m = jabber.Message(getjid(who), msg)
	m.setFrom(JID)
	m.setType('chat')
	if conf.general.debug > 1:
		print '...Begin....................', who
	con.send(m)
	#	time.sleep(.1)
	

def sendtoall(msg,butnot=[],including=[], status = None):
	global lastlog
	r = con.getRoster()
	print >>logf,time.strftime("%Y-%m-%d %H:%M:%S"), msg.encode("utf-8")
	logf.flush()
	if conf.general.debug:
		try:
			print time.strftime("%Y-%m-%d %H:%M:%S"), msg.encode(locale.getdefaultlocale()[1],'replace')
		except:
			print time.strftime("%Y-%m-%d %H:%M:%S"), msg.encode("utf-8")
	for i in r.getJIDs():
		#print i, uset.mutechange.get(i)
		#away represents users that don't want to chat
		if getdisplayname(i) in butnot or has_userflag(getcleanname(i), 'away'): 
			continue
		#if status == 1 and uset.mutechange[i] == 1:
		#	continue
		state=r.isOnline(i)
		if r.isOnline(i) and r.getShow(i) in ['available','chat','online',None]:
			sendtoone(i, msg)
	if not msg.startswith(conf.general['sysprompt']):
		lastlog.append(msg)
	if len(lastlog)>5:
		lastlog=lastlog[1:]
		
def sendtoadmin(msg,butnot=[],including=[]):
	global lastlog
	r = con.getRoster()
	print >>logf,time.strftime("%Y-%m-%d %H:%M:%S"), msg.encode("utf-8")
	logf.flush()
	if conf.general.debug:
		try:
			print time.strftime("%Y-%m-%d %H:%M:%S"), msg.encode(locale.getdefaultlocale()[1],'replace')
		except:
			print time.strftime("%Y-%m-%d %H:%M:%S"), msg.encode('utf-8')
	for i in r.getJIDs():
		#away is represent user don't want to chat
		if not issadmin(i) or getdisplayname(i) in butnot or has_userflag(getcleanname(i), 'away'):
			continue
		state=r.getShow(unicode(i))
		if state in ['available','chat','online',None] or getdisplayname(i) in including :
			sendtoone(i,msg)
			time.sleep(.2)
	if not msg.startswith(conf.general['sysprompt']):
		lastlog.append(msg)
	if len(lastlog)>5:
		lastlog=lastlog[1:]

#================================
#=         Sys Messages         =
#================================
def systoall(msg, butnot=[], including=[], status = None):
	user = butnot[:]
	for i in userinfo.keys():
		if has_userflag(i, 's'):
			user.append(i)
	sendtoall(conf.general['sysprompt'] + ' ' + msg, user, including, status)
	
def systoone(who, msg):
#	if not has_userflag(getjid(who), 's'):
	sendtoone(who, conf.general['sysprompt'] + ' ' + msg)
	
def systoadmin(msg, butnot=[], including=[]):
	sendtoadmin(conf.general['sysprompt'] + ' ' + msg, butnot, including)

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
	if not conf.general['hide_status']:
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
#	con.removeRosterItem(jid)

#=====================================================
#=         Chat Commands                             =
#=====================================================
def cmd(who,msg):
	if " " in msg:
		cmd,msg=msg.split(" ",1)
	else:
		cmd,msg=msg.strip().lower(),""
	if cmd[:1] in commandchrs:
		cmd=cmd[1:]
		
	cmd = cmd.lower()
	func = None
	try:
		if commands.has_key(cmd):
			if iscuss(msg):
				raise CUSS_COMMAND
			func = commands[cmd]
			func(who, msg)
		elif acommands.has_key(cmd):
			if issadmin(who):
				func = acommands[cmd]
				func(who, msg)
			else:
				raise ADMIN_COMMAND
		else:
			systoone(who, _('Unknown command "%s".').para(cmd))
	except ADMIN_COMMAND:
		systoone(who, _('This is admin command. You are _*not*_ an admin.'))
	except CUSS_COMMAND:
		systoone(who, _('Please refrain from the use of foul language.'))
	except TOOLOW_COMMAND:
		systoone(who, _('You cannot use this command against a Super Admin.'))
	except CUSS_COMMAND:
		systoone(who, _('Please refrain from the use of foul language.'))
	except MSG_COMMAND:
		f = _
		systoone(who, f(func.__doc__))
	except NOMAN_COMMAND:
		systoone(who, _('There is no this person'))

#=====================================================
#=         User Commands                             =
#=====================================================
#=================================
#=         Self Commands         =
#=================================
def cmd_nick(who, msg):
	'Type /nick help for more information.'
	if issadmin(who.getStripped()):
		msg = msg.strip().lower()
	else:
		msg = msg.strip('_*').lower() #Limits the abuse of capitals and makes it harder to steal names.
	#= Must be here or nicklist.ini will get corrupted if it encounters an unknown character.
	try:
		msg = msg.encode(locale.getdefaultlocale()[1],'replace')
	except:
		msg = msg.encode("utf-8")
	nickname = wid = who.getStripped()
	nickconf = nick['nickname']
	nicknow = None
	if nick['nickname'].get(getjid(who)):
		nicknow = nick['nickname'].get(getjid(who)).lower()
	
	#==================
	#= Check for commands that have an optional secondary command first.
	if 'list' in msg:
		if ' ' in msg:
			cmd, msg = msg.split(' ', 1)
			if msg == 'online':
				r = con.getRoster()
				names = []
				for i in nick.nickname.keys():
					state = r.getOnline(unicode(i))
					name = getdisplayname(i)
					if state in ['available','chat','online',None] or isbusy(i):
						names.append('%s  :  %s\n' % (name, i))
				systoone(who, _('Names: total (%d)\n%s').para(len(names), " ".join(names)))
		elif ' ' not in msg or msg != 'online':
			names = []
			for i in nick.nickname.keys():
				name = getdisplayname(i)
				names.append('%s  :  %s\n' % (name, i))
			systoone(who, _('Names: total (%d)\n%s').para(len(names), " ".join(names)))
	
	#==================
	#= Check if the user wants to do something with the nick.
	elif ' ' in msg:
		name, msg = msg.split(' ', 1)
		namecap = name.capitalize()
		if len(name) > conf.general['maxnicklen']:
			systoone(who, _('Please use a nick shorter than %d. Thank you.').para(conf.general['maxnicklen']))
		elif msg in ('register', 'reg'):
			if name in nick.nickreg.keys():
				systoone(who, _('The nick %s has already been regestered to %s.').para(namecap,nick.nickreg[name]))
			else:
				if nicknow != None:
					del nick.tempnick[nicknow]
				del nick.tempnick[name]
				nick.nickreg[name] = wid
				nick.nickname[nickname] = namecap
				systoone(who, _('The nick %s has now been regestered to your email address.').para(namecap))
		elif msg in ('unreg', 'unregister'):
			if wid != nick.nickreg[name]:
				systoone(who, _('How _*dare*_ you try to steal the nick %s from %s?!').para(namecap,nick.nickreg[name]))
			else:
				del nick.nickreg[name]
				del nickconf[wid]
				systoone(who, _('Anyone can now use the nick %s.').para(namecap))
		else:
			systoone(who, _('Please check what you typed is:\n1. a name with no spaces in it\n2. a valid command\n if it is both of these please report the but to an admin.'))
	
	elif msg == 'help':
		systoone(who, _('Useage: "/nick <nickname> [<command>]"\nCommands:\nlist [online] - Displays a list of nicknames and the emails of the user.\nreg(ister) - Regesters the nickname to your email\nunreg(ister) - Unregisters the nickname from your email'))
	
	#===================
	#= Set the users nick as msg.
	elif msg:
		msgcap = msg.capitalize()
		if len(msg) > conf.general['maxnicklen']:
			systoone(who, _('Please use a shorter name. Thank you.'))
		elif msg in nick.nickreg.keys() and wid != nick.nickreg[msg]:
			systoone(who, _('The nick _%s_ has already been regestered to %s.').para(msg,nick.nickreg[msg]))
		elif msg in nick.tempnick.keys() and wid != nick.tempnick[msg]:
			systoone(who, _('The nick _%s_ is already being used by %s.').para(msgcap,nick.tempnick[msg]))		
		else:
			systoone(who, _('You will now send messages as <%s>').para(msgcap))
			del nick.tempnick[nicknow]
			if msg not in nick.tempnick.keys() and msg not in nick.nickreg.keys():
				nick.tempnick[msg] = wid	
			nick.nickname[nickname] = msgcap
			
	#===================
	#= If the user has a nick remove it else display MSG_COMMAND.
	else:
		if hasnick(wid):
			del nick['nickname'][wid]
			systoone(who, _('You will now send messages as <%s>').para(getdisplayname(who)))
			saveconfig()
		else:
			raise MSG_COMMAND
	savenicklist()

def cmd_me(who, msg):
	'"/me <msg>" Says an emote as you'
	if msg == "":
		raise MSG_COMMAND
	else:
		sendtoall(_('**%s %s**').para(getdisplayname(who),msg))
		
def cmd_smite(who, msg):
	'"/smite" smites someone. Syntax: /smite person'
	if msg.strip().lower() == "":
		systoone(who, _('It works like /smite person'))
	else:
		smitee = msg.title()
	if smitee == "Chuck Norris":
		systoall(_('Chuck Norris resents the smite attempt and roundhouse kicks %s in the face').para(getdisplayname(who)))
	else:
		systoall(_('%s smites %s').para(getdisplayname(who),smitee))
		
def cmd_help(who, msg):
	'"/help" Show this help message'
	if msg == 'nick':
		systoone(who, _('Useage: "/nick <nickname> [<command>]"\nCommands:\nreg(ister) - Regesters the nickname to your email\nunreg(ister) - Unregisters the nickname from your email'))
	else:
		jid = who.getStripped()
		f = _
		systoone(who, _('Commands: \n%s').para(' /' + ' /'.join(["%-20s%s\n" % (x, unicode(f(y.__doc__, get_userlang(jid))) or "") for x, y in commands.items()])))
		if issadmin(who.getStripped()):
			systoone(who, _('Admin commands: \n%s').para(' /' + ' /'.join(["%-20s%s\n" % (x, unicode(f(y.__doc__, get_userlang(jid))) or "") for x, y in acommands.items()])))
		systoone(who, _('See http://coders.meta.net.nz/~perry/jabber/confbot.php for more details.\nAlso see http://www.donews.net/limodou for Chinese version.'))

def cmd_w(who, msg):
	cmd_names(who, msg)
		
def cmd_who(who, msg):
	cmd_names(who, msg)
		
def cmd_names(who, msg):
	'"/names" List all the people in the room'
	r = con.getRoster()
	names = []
	for i in r.getJIDs():
		if '@' not in unicode(i):
			continue
		state = r.getOnline(unicode(i))
		name = getdisplayname(i)
		if issuper(i.getStripped()):
			name = "@%s" % name
		if isadmin(i.getStripped()):
			name = "%"+"%s" % name
		if has_userflag(i.getStripped(), 'away'):
			name = "-%s" % name
		if has_userflag(i.getStripped(), 'banned'):
			name = "#%s" % name
		if isbusy(i.getStripped()):
			name = "!%s" % name
		if state in ['available','chat','online',None]:
			names.insert(0,name)
		else:
			names.append('(%s)' % name)
	systoone(who, _('Names: total (%d)\n%s').para(len(names), " ".join(names)))
	
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
			systoone(who, _('<%s> has set himself in "away" mode, so you could not send him a message.').para(getdisplayname(target))) 
			return
		if isbusy(target):
			systoone(who, _('<%s> has set themselves as busy or is idle so the message has not been delivered.').para(getdisplayname(target)))
			return
		if not userinfo.has_key(getjid(target)):
			raise NOMAN_COMMAND
		sendtoone(getjid(target), _('*<%s>* %s').para(getdisplayname(who), msg))
		systoone(who, _('>%s> %s').para(getdisplayname(target), msg))
		
		
#===================================
#=         Option Commands         =
#===================================
usettings = ['mutechange']
def cmd_settings(who, msg):
	'Type /settings help for more information.'
	msg = msg.strip().lower()
	jid = getjid(who.getStripped())
	if msg:
		if ' ' in msg:
			setting, msg = msg.split(' ', 1)
		else:
			setting = msg
		#print setting, msg
		if setting in usettings:
			if msg:
				#set, msg = msg.split(' ', 1)
				if setting in ('mutechange'):
					if msg in ('1', 'yes', 'on', 'true'):
						value = 1
					else:
						value = 0
				uset[setting][jid] = value
				saveuset()
				readuset()
			else:
				value = uset[setting][jid]
			if setting in ('mutechange'):
				if uset[setting][jid]:
					value = 'On'
				else:
					value = 'Off'
			systoone(jid, _('%s is currently %s').para(setting ,value))
		else:
			systoone(jid, _('The setting you\'re trying to change doesn\'t seem to exist.'))
	elif msg == 'help':
		systoone(jid, _('''Useage: /settings <setting> <value>
			Settings:
			mutechange - Mute the announcement when a user comes online, is busy or idle, and goes offline.'''))
	
	else:
		raise MSG_COMMAND
	saveuset()
	
def cmd_lang(who, msg):
	'"/lang [language]" Set language to "language" or reset to default'
	msg = msg.strip().lower()
	if msg:
		add_langflag(who.getStripped(), '*%s' % msg)
		systoone(who, _('Your language has been set as "%s".').para(msg))
	else:
		del_langflag(who.getStripped())
		systoone(who, _('Your language has been set as default.'))
		
def cmd_listlangs(who, msg):
	'"/listlangs" List all support language'
	systoone(who, _('Available languages: %s').para(' '.join(i18n.listlang())))
	
def cmd_vcard(who, msg):
	'"/vcard" usage: /vcard full name**personal quote**website address. ** is the field seperator.'
	if not msg:
		systoone(who, _('"/vcard" usage: /vcard full name**personal quote**website address. ** is the field seperator.'))
	else:
		name, quote, addy = msg.split("**",3)
		addy = re.sub("http://","",addy)
		systoone(who, _('INFO FOR %s: \n Name: %s \n Personal Quote: "%s" \n Web Address: http://%s').para(getdisplayname(who),name,quote,addy))

#===================================
#=         Status Commands         =
#===================================
def cmd_leave(who, msg):
	'"/leave" The same as /quit'
	cmd_quit(who, msg)
	
def cmd_exit(who, msg):
	'"/exit" The same as /quit'
	cmd_quit(who, msg)

def cmd_quit(who, msg):
	'"/quit" Quit this room for ever'
	if msg:
		msg = "(%s)" % msg
	systoall(_('Quit: <%s> %s').para(getdisplayname(who)),msg)
	if not issuper(who):
		boot(who.getStripped())

def cmd_away(who, msg):
	'"/away [message]" Set "away"(need message) or "chat"(no message) flag of someone' 
	msg = msg.strip().lower()
	if msg or not has_userflag(who.getStripped(), 'away'):
		cmd_nochat(who, msg)
	else:
		cmd_chat(who, msg)
		
def cmd_nochat(who, msg):
	'"/nochat [message]" Set "away" flag of someone, just like "/away message"'
	add_userflag(who.getStripped(), 'away')
	if msg:
		msg = "(%s)" % msg
	systoall(_('%s is temporarily away. %s').para(getdisplayname(who), msg), [who])
	systoone(who, _('Warning: Because you set "away" flag, so you can not receive and send any message from this bot, until you reset using "/away" or "/chat" command or just send a message to the chatroom.')) 
	
def cmd_chat(who, msg):
	'"/chat" Remove "away" flag of someone, just like "/away"'
	if has_userflag(who.getStripped(), 'away'):
		del_userflag(who.getStripped(), 'away')
		systoall(_('%s is actively interested in chatting.').para(getdisplayname(who)), [who])
		systoone(who, _('You can begin to chat now.'))
	else:
		systoone(who, _('You didn\'t set _away_ flag.'))
		
def cmd_mode(who, msg):
	'"/mode option" Set or remove flag to someone. For example: "+s" filter system message, "-s" receive system message'
	msg = msg.strip().lower()
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


#=================================
#=         Misc Commands         =
#=================================
def cmd_version(who, msg):
	'"/version" Show version of this bot'
	systoone(who, _('''Revision: %s 
	
	Websites:
	English:
	http://coders.meta.net.nz/~perry/jabber/confbot.php
	Chinese:
	http://www.donews.net/limodou.''').para(revision))
	
def cmd_die(who, msg):
	'"/die" rolls a random number'
	systoall(_('%s rolls a %s').para(getdisplayname(who,1),random.randrange(1,7)))

def cmd_dice(who, msg, j = 0, i = 0, dice = 1):
	'"/dice [<number of dice>] [<number of sides>]" rolls a random number'
	if not msg:
		cmd_die(who, msg)
	
	elif msg:
		if msg == 'help':
			raise MSG_COMMAND
		else:
			if ' ' in msg:
				dice, msg = msg.split(' ',2)
				if dice.isdigit() and msg.isdigit():
					if int(dice) > 20:
						systoone(who, _('The number of dice is auto capped at 20.'))
					if int(msg) <= 3:
						systoone(who, _('Please choose 4 or more sides'))
					else:
						while int(j) < int(dice) and int(j) < 20:
							j = int(j) + 1
							i = i + random.randrange(1,int(msg))
						systoall(_('%s rolls %s with %s %s-sided dice').para(getdisplayname(who,1),i,j,msg))
								
				else:
					raise MSG_COMMAND
			
			else:
				if msg.isdigit():
					if int(msg) > 20:
						systoone(who, _('The number of dice is auto capped at 20.'))
					while int(j) < int(msg) and int(j) < 20:
						j = int(j) + 1
						i = i + random.randrange(1,7)
					systoall(_('%s rolls %s with %s dice').para(getdisplayname(who,1),i,j))
	
	else:
		raise MSG_COMMAND
def cmd_whois(who, msg):
	'"/whois [nick]" View someone\'s status'
	msg = msg.strip().lower()
	jid = getjid(msg)
	if msg and issadmin(who.getStripped()):
		if userinfo.has_key(jid):
			status = userinfo[jid]
			systoone(who, _('Info: %s').para(" ".join(status)))
		else:
			raise NOMAN_COMMAND
	else:
		status = userinfo[who.getStripped()]
		systoone(who, _('Info: %s').para(" ".join(status)))
	
def cmd_getemail(who, x):
	'"/getemail <nickname>" Returns a users email address from their nickname.'
	if msg:
		getjid(x)
	else:
		raise MSG_COMMAND

def cmd_filterlist(who, msg):
		'Displays a list of filtered words.'
		filter = convert_seq(conf.general.get("wordfilter"), y = 2)
		systoone(who, _('The words currently filtered are:\n%s').para(filter))

def cmd_info(who, msg):
	'Useage: /info <nickname>'
	if msg:
		i = getjid(msg.strip().lower())
		r = con.getRoster()
		#resource = j.getResource()
		status = r.getStatus(unicode(i))
		show = r.getShow(unicode(i))
		online = r.getOnline(unicode(i))
		sub = r.getSub(unicode(i))
		name = r.getName(unicode(i))
		ask = r.getAsk(unicode(i))
		#systoone(who, _("Resource: %s").para(resource))
		systoone(who, _("Status: %s").para(status))
		systoone(who, _("Show: %s").para(show))
		systoone(who, _("Online: %s").para(online))
		systoone(who, _("Sub: %s").para(sub))
		systoone(who, _("Name: %s").para(name))
		systoone(who, _("Ask: %s").para(ask))
		#print "Summary", r.getSummary()
	else:
		raise MSG_COMMAND
	
	
#=====================================================
#=         Admin Commands                            =
#=====================================================
#=================================
#=         User Commands         =
#=================================	
def acmd_invite(who, msg):
	'"/invite nick" Invite someone to join this room'
	jid = getjid(msg.strip().lower())
	if msg:
		con.send(jabber.Presence(to=jid, type='subscribe'))
		adduser(jid)
		systoone(who, _('Invited <%s>').para(jid))
	else:
		raise MSG_COMMAND

def acmd_mute(who, msg):
	'"/mute nick" Mute someone'
	jid = getjid(msg.strip().lower())
	if msg:
		if ismuted(jid):
			delmute(jid)
			systoone(who, _('<%s> has been unmuted').para(getdisplayname(jid)))
			systoone(jid, _('You have been unmuted by <%s>').para(getdisplayname(who)))
		elif not issadmin(jid) and not who == jid:
			addmute(jid)
			systoone(who, _('<%s> has been muted.').para(getdisplayname(jid)))
			if ' ' in msg:
				mutee, msg = msg.split(' ',1)
				systoone(jid, _('<%s> has muted you for %s.').para(getdisplayname(who,1), msg))
			else:
				systoone(jid, _('<%s> has muted you.').para(getdisplayname(who,1)))
	else:
		raise MSG_COMMAND	
	
def acmd_boot(who, msg):
	'"/boot" The same as /kick'
	acmd_kick(who, msg)
	
def acmd_kick(who, msg):
	'"/kick nick" Kick someone out of this room'
	jid = getjid(msg.strip().lower())
	if isadmin(who.getStripped()) and issuper(jid):
		act = "kick"
		print time.strftime("%Y-%m-%d %H:%M:%S"), getjid(who), "has tried to", act,"the Super Admin", jid
		raise TOOLOW_COMMAND
	else:		
		if userinfo.has_key(jid):
			boot(jid)
			del userinfo[jid]
			saveconfig()
			systoall(_('Booted: <%s>').para(getdisplayname(jid,1)))

def acmd_ban(who, msg):
	'"/ban nick" Forbid someone rejoin this room'
	jid = getjid(msg.strip().lower())
	if msg:
		if isadmin(who.getStripped()) and issuper(jid):
			act = "ban"
			print time.strftime("%Y-%m-%d %H:%M:%S"), getjid(who), "has tried to", act,"the Super Admin", jid
			raise TOOLOW_COMMAND
		else:		
			if userinfo.has_key(jid):
				boot(jid)
			addban(msg)
			systoall(_('Banned: <%s>').para(getdisplayname(msg,1)))
	else:
		raise MSG_COMMAND

def acmd_unban(who, msg):
	'"/unban <nick>" Permit someone rejoin this room'
	jid = getjid(msg.strip().lower())
	if msg:
		if delban(jid):
			deluser(jid)
			systoone(who, _('Unbanned: <%s>').para(jid))
		else:
			systoone(who, _('%s is not banned').para(jid))
	else:
		raise MSG_COMMAND

def acmd_addadmin(who, msg):
	'"/addadmin <nick>" Set someone as administrator'
	jid = getjid(msg.strip().lower())
	if msg:
		if who.getStripped() != jid:
			addadmin(jid)
			systoone(who, _('Added <%s>').para(jid))
			systoone(jid, _('<%s> added you as an admin').para(getdisplayname(who,1)))
		else:
			systoone(who, _('You are an admin already.'))
	else:
		raise MSG_COMMAND
		
def acmd_deladmin(who, msg):
	'"/deladmin <nick>" Remove admin right from someone'
	jid = getjid(msg.strip().lower())
	if msg:
		if issuper(jid):
			systoone(who, _('<%s> is a super admin which can not be deleted.').para(jid))
		else:
			if deladmin(jid):
				systoone(who, _('Removed <%s>').para(jid))
				systoone(getjid(msg), _('<%s> removed you as an admin').para(getdisplayname(who,1)))
			else:
				systoone(who, _('<%s> is not an admin').para(jid))
	else:
		raise MSG_COMMAND
		
def acmd_anick(who,msg):
	'"/anick" Type /anick help for more information.'
	msg = msg.strip().lower()
	if ' ' in msg:
		name, msg = msg.split(' ', 2)
		namecap = name.capitalize()
		if msg in ('unreg', 'unregister'):
			njid = nick['nickreg'].get(name, "")
			del nick.nickreg[name]
			if nick.nickname[njid] == name:
				del nick.nickname[njid]
			systoone(who, _('Anyone can now use the nick %s.').para(namecap))
		else:
			systoone(who, _('Please check what you typed is:\n1. a name with no spaces in it\n2. a valid command\n if it is both of these please report the but to an admin.'))
	
	elif msg in ('list', 'names'):
			names = []
			for i in nick.nickname.keys():
				name = getdisplayname(i,1)
				names.append('%s : %s\n' % (name, i))
			systoone(who, _('Names: total (%d)\n%s').para(len(names), " ".join(names)))
	
	elif msg == 'help':
		systoone(who, _('Useage: "/nick <nickname> <command> [<extra>]"\nCommands:\nunreg(ister) - Unregisters the nickname from the nicklist'))
		
#=================================
#=         Room Commands         =
#=================================
def acmd_status(who, msg):
	'"/status [message]" Set or see the bot\'s status'
	msg = msg.strip().lower()
	if msg:
		conf.general['status'] = msg
		saveconfig()
		sendpresence(msg)
		systoone(who, _('Status has been set as: %s').para(msg))
	else:
		systoone(who, _('Status is: %s').para(conf.general['status']))
		
def acmd_kill(who, msg):
	'"/kill [message]" Close the room'
	msg = msg.strip().lower()
	if msg:
		systoall(_('Room shutdown by <%s> (%s)').para(getdisplayname(who),msg))
	else:
		systoall(_('Room shutdown by <%s>').para(getdisplayname(who)))
	sys.exit(1)
	
def acmd_refresh(who, msg):
	'"/refresh" Update the conference bot website'
	if not running:
		t = threading.Thread(target=register_site)
		t.setDaemon(True)
		t.start()
		systoone(who, _('Refreshing the website'))
	else:
		systoone(who, _('Refresh already in progress'))
		
def acmd_reload(who, msg):
	'"/reload" Reload the config'
	readall()
	wordfilter = cuss_list()
	systoone(who, _('Bot reloaded.'))

		
#===============================
#=         DB Commands         =
#===============================
options = ['language', 'private', 'hide_status', 'debug', 'topic', 'sysprompt', 'logfileformat', 'status', 'maxnicklen', 'filtermask', 'floodback']
def acmd_setoption(who, msg):
	'"/setoption option value" Set an option\'s value'
	msg = msg.strip().lower()
	if not msg or ' ' not in msg:
		raise MSG_COMMAND
	else:
		option, msg = msg.split(' ', 1)
		if option in options:
			if option in ('private', 'hide_status', 'floodback'):
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
			conf.general[option] = value 
			saveconfig()
			readconfig()
			systoone(who, _('Success'))
		else:
			systoone(who, _('Option [%s] may not exist or can not be set.').para(option))
			
def acmd_listoptions(who, msg):
	'"/listoptions" List all options that can be changed'
	msg = msg.strip().lower()
	txt = []
	for option in options:
		if option in ('private', 'hide_status', 'floodback'):
			if conf.general[option]:
				value = 'On'
			else:
				value = 'Off'
		else:
			value = conf.general[option]
		txt.append("%s : %s" % (option, value))
	systoone(who, _('Options: \n%s').para('\n'.join(txt)))

def acmd_filter(who, msg):
	'Same thing as /wordfilter'
	acmd_wordfilter(who, msg)
		
def acmd_wordfilter(who, msg):
	'"/filter" Type /wordfilter help for more information.'
	if issadmin(who.getStripped()):
		if ' ' in msg:
			cmd, msg = msg.split(' ', 1)
			if cmd == 'add':
				if len(msg) < 3:
					systoone(who, _('You may not filter words with less than 3 letters in them.'))
				else:
					addfilter(msg)
					systoone(who, _('Added %s to the filter list').para(msg))
			
			elif cmd in ('del','delete','remove'):
				if del_flag('wordfilter',msg):
					systoone(who, _('Deleted %s from the filter list').para(msg))
					
				#==================
				#= Checks for filters with u"" around them.
				else:
					if del_flag('wordfilter','u"' + msg + '"'):
						systoone(who, _('Deleted %s from the filter list').para(msg))
					else:
						systoone(who, _('This filter doesn\'t exist'))
						
			elif cmd in ('filter', 'mask'):
				conf.general['filtermask'] = msg
				systoone(who, _('Filtered words will now be masked by %s.').para(msg))
			
		elif msg == 'help':
			systoone(who, _('''Useage: /filter [<command> <filter>]
			Commands:
			/filter - Displays the list of currently filtered words.
			Add - Adds a filter ot the list.
			Del - Deletes a filter from the list.
			Mask - Changes the filter mask.'''))
		
		else:
			filter = convert_seq(conf.general.get("wordfilter"), y = 2)
			systoone(who, _('The words currently filtered are:\n%s').para(filter))
	else:
		filter = convert_seq(conf.general.get("wordfilter"), y = 2)
		systoone(who, _('The words currently filtered are:\n%s').para(filter))

	readconfig()
	saveconfig()
	wordfilter = cuss_list()
		
#=================================
#=         Misc Commands         =
#=================================
def acmd_qna(who, msg, butnot=[], including=[], status = None):
	'"/qna" Start a Question and Answer game'
	
	user = butnot[:]
	
	global qu, an, ra
	Qs = games.Qs
	As = games.As
	Ps = games.Ps
	qnalist = games.QnA
	
	#=======================
	#= Get the list of lists
	list = qnalist.keys()
	ra = random.randrange(1,len(list))
	list = list[ra]
	
	#=======================
	#= Check to see if the list should be used.
	while qnalist[list] == 0:
		ra = random.randrange(1,len(list))
		list = list[ra]
		
	#======================
	#= Set the lists to be used.
	prefix = Ps[list][0]
	qu = Qs[list]
	an = As[list]
	listq = len(qu)
	ra = None
	
	if msg:
		systoone(who, _('Currently under construction.'))

	else:
		nra = random.randrange(1,listq)
		while nra == ra:
			nra = random.randrange(1,listq)
		ra = nra
		systoall('Question and Answer')
		sendtoall(prefix +" "+ qu[ra], user, including, status)
		qna = an[ra]

def acmd_spam(who, msg):
	msg = msg.lower()
	if ' ' in msg:
		i = 0
		nick, msg = msg.split(' ', 1)
		while int(i) <= int(msg):
			sendtoone(nick, 'SPAM!')
			i = i + 1
	else:
		systoone(who, _('Use it /spam <nick> <number>'))
#========================================
#=         Depreciated Commands         =
#========================================
#===================================================
#=         End Commands                            =
#===================================================		

def sendpresence(msg):
	p = jabber.Presence()
	p.setStatus(msg)
	con.send(p)


#===================================================
#=         Pre-Message Formating                   =
#===================================================
def messageCB(con,msg):
	global ontesting
	whoid = getjid(msg.getFrom())
	if conf.general.debug > 2:
		try:
			print '>>>', time.strftime('%Y-%m-%d %H:%M:%S'), '[MESSAGE]', unicode(msg).encode(locale.getdefaultlocale()[1])
		except:
			print '>>>', time.strftime('%Y-%m-%d %H:%M:%S'), '[MESSAGE]', unicode(msg).encode('utf-8')
	if msg.getError()!=None:
		if conf.general.debug > 2:
			try:
				print '>>> [ERROR]', unicode(msg).encode(locale.getdefaultlocale()[1])
			except:
				print '>>> [ERROR]', unicode(msg).encode('utf-8')
		#if statuses.has_key(getdisplayname(msg.getFrom())):
		#	sendstatus(unicode(msg.getFrom()),_("away"), _("Blocked"))
		#boot(msg.getFrom().getStripped())
	elif msg.getBody():
		#check quality
		if msg.getFrom().getStripped() == getjid(JID):
			body = msg.getBody()
			if body and body[0] == 'Q':
				ontesting = False
				t = int(body[1:].split(':', 1)[0])
				t1 = int(time.time())
				if t1 - t > reconnectime:
					if conf.general.debug > 1:
						print '>>>', time.strftime('%Y-%m-%d %H:%M:%S'), 'RECONNECT... network delay it too long: %d\'s' % (t1-t)
					raise RECONNECT_COMMAND
			xmllogf.flush()
			return
		userjid[whoid] = unicode(msg.getFrom())
		if len(msg.getBody())>1024 and not issadmin(whoid):
			if conf.general['floodback'] == 1:
				i = 0
				while i <= 10:
					systoone(whoid, _('Thank you for trying to flood our chat room. Here is some refreshing water for you.'))
					i = i + 1
				return
			#systoall(_("%s is being a moron trying to flood the channel").para(getdisplayname(msg.getFrom())))
		elif ismuted(whoid):
			systoone(whoid, _('You are muted and cannot talk.'))
		elif msg.getBody()[:1] in commandchrs:
			if conf.general.debug > 1:
				print '......CMD......... %s [%s]' % (msg.getFrom(), msg.getBody())
			cmd(msg.getFrom(),msg.getBody())
		else:
			#check away
			if has_userflag(msg.getFrom().getStripped(), 'away'):
				del_userflag(msg.getFrom().getStripped(), 'away')
				#systoone(msg.getFrom().getStripped(), _('Warning: Because you set "away" flag, so you can not receive and send any message from this bot, until you reset using "/away" command'))
				#xmllogf.flush()
				#return
			global suppressing,last_activity
			suppressing=0
			last_activity=time.time()
			msgfilter = re.sub(wordfilter,conf.general.get('filtermask'), msg.getBody())
			sendtoall('<%s> %s' % (getdisplayname(msg.getFrom()),msgfilter),
				butnot=[getdisplayname(msg.getFrom())],
				)
			
			#==================
			#= Extra Message Handlers
			if os.path.getsize("Games.ini") != 0:
				global ra
				if ra:
					if an[ra].lower() in msg.getBody().lower():
						systoall (_('%s got the answer to \"%s\" right!').para(getdisplayname(whoid,1), qu[ra]))
						score = 1
						if games['QnA Scores'].get(whoid, ""):
							score = 1 + int(games['QnA Scores'].get(whoid, ""))
						games['QnA Scores'][whoid] = score
						ra = None
						saveGames()
			if isbusy(msg.getFrom().getStripped()):
				systoone(msg.getFrom(), _('Warning: You are marked as "busy" in your client,\nyou will not see other people talk,\nset yourself "available" in your client to see their replies.'))
	xmllogf.flush() # just so flushes happen regularly


def presenceCB(con,prs):
	if conf.general.debug > 3:
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
		elif conf.general['private'] and not isuser(prs.getFrom().getStripped()):
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
		systoone(who, wel % {'revision':revision})
		systoone(who, _('''Topic: %(topic)s
			%(lastlog)s''').para({
			"topic" : conf.general['topic'],
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
		elif show in ['xa', 'away', 'dnd']:
			sendstatus(who, _('away'),prs.getStatus())
		else:
			sendstatus(who, _('away'),show+" [[%s]]" % prs.getStatus())
		userjid[whoid] = who
	elif type == 'unavailable':
		status = prs.getShow()
		sendstatus(who, _('away'),status)
	else:
		if conf.general.debug > 3:
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
	
def saveall():
	try:
		saveconfig()
		savenicklist()
		saveGames()
	except:
		traceback.print_exc()
		
def readall():
	readconfig()
	readnicklist()
	readGames()
	
def readconfig():
	global conf, welcome, userinfo

	conf = DictIni()
	
	#=======================
	#= General Config
	conf.general.server = 'gmail.com'
	conf.general.resource = 'conference'
	conf.general.private = 0
	conf.general.hide_status = 0
	conf.general.debug = 1
	conf.general.configencoding = 'utf-8'
	conf.general.sysprompt = '***'
	conf.general.logpath = 'logs'
	conf.general.language = ''
	conf.general.logfileformat = '%Y%m%d'
	conf.general.status = _('Ready')
	conf.general.filtermask = '<Censored>'
	conf.general.maxnicklen = 10
	conf.general.floodback = 0
	conf.general.wordfilter = 'fuc*k','shit','damn','mofo','nigger',
	
	if len(sys.argv)>1:
		conf.setfilename(sys.argv[1])
		conf.read(sys.argv[1])
	else:
		conf.setfilename("config.ini")
		conf.read("config.ini")
		
	#get real value
	readoptionorprompt('general', "account", _("What is the account name of your bot:"))
	readoptionorprompt('general', "password", _("What is the password of your bot:"))
	readoptionorprompt('general', "topic", _("Write a short description about your bot:"))
	
	#encoding convert
	encoding = conf.general.configencoding
	conf.general.sysprompt = i18n.Unicode(conf.general.sysprompt, encoding)
	conf.general.topic = i18n.Unicode(conf.general.topic, encoding)
	conf.general.status = i18n.Unicode(conf.general.status, encoding)

	for key, flags in conf.userinfo.items():
		if 'super' in flags: break
	else:
		print _("Input super admin email account:"),
		admin = raw_input().lower()
		conf.userinfo[admin] = ['user', 'super']
			
	#deal with welcome message
	if os.path.exists('welcome.txt'):
		welcome = unicode(file('welcome.txt').read(), encoding)

	userinfo = conf.userinfo
			
def saveconfig():
	"Saves the config to disk"
	try:
		#encoding convert
		encoding = conf.general.configencoding
		conf.general.sysprompt = conf.general.sysprompt.encode(encoding)
		conf.general.topic = conf.general.topic.encode(encoding)
		conf.general.status = conf.general.status.encode(encoding)
		
		conf.save()
		file('welcome.txt', 'w').write(welcome.encode(encoding))
	except:
		traceback.print_exc()
		
def readnicklist():
	global nick

	nick = DictIni()
	
	nick.setfilename("nicklist.ini")
	nick.read("nicklist.ini")
		
def savenicklist():
	"Saves the nicklist to disk"
	try:	
		nick.save()
	except:
		traceback.print_exc()
		
def readGames():
	global games

	games = DictIni()
	
	games.setfilename("Games.ini")
	games.read("Games.ini")
		
def saveGames():
	"Saves the Games to disk"
	try:	
		games.save()
	except:
		traceback.print_exc()
		
def connect():
	global con, revision
	debug = conf.general.debug
	
	revision = get_svn_version()
	
	print ">>> Connecting"
	general = conf.general
	if debug:
		print '>>> debug is [%d]' % general['debug']
		print '>>> host is [%s]' % general['server']
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
			adduser(getcleanname(i))
			
	saveconfig()
	sendpresence(conf.general['status'])
	
#	systoall(_('The channel has started.'))
	print '>>> Online with Revision %d' % revision
	print >>logf, 'The bot is started!', time.strftime('%Y-%m-%d %H:%M:%S')
	

def register_site():
	global last_update, running
	
	running = True
	
	general = conf.general
	print '>>> Registing site'
	roster=con.getRoster()
	args={
		'action':'register',
		'account':"%s@%s" % (general['account'], general['server']),
		'users':len(con.getRoster().getJIDs()),
		'alive_users':len([i 
			for i in roster.getJIDs() 
			if roster.getOnline(unicode(i)) in ['available','chat','online',None]
			]),
		'last_activity':time.time()-last_activity,
		'admin':' '.join(
			[ k 
				for k,v in userinfo.items() 
				if "super" in v
			]),
		'lang': conf.general['language'],
		'version':revision,
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
	
readall()
saveall()
wordfilter = cuss_list()

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

general = conf.general

#logfile process
if not os.path.isdir(general['logpath']) and not general['logpath'] == '':
	os.mkdir(general['logpath'])
	print "ALERT: Directory doesn't exist, making folder \""+ general['logpath'] +"\""
logf = file(os.path.join(general['logpath'], time.strftime(general['logfileformat']) + '.log'), "a+")

con = None
JID="%s@%s/%s" % (general['account'], general['server'], general['resource'])
last_update=(time.time()-4*60*60)+60 # Send the update in 60 seconds
last_ping=0
last_testing=0
userjid = {}	#saving real jid just like "xxx@gmail.com/gtalkxxxxx"
reconnectime = 30	#network delay exceed this time, so the bot need to reconnect

ontesting = False

running = False
while 1:
	try:
		#create new log file as next day
		general = conf.general
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
		# Send some kind of dummy message every few minutes to make
		# sure that the connection is still up, and to tell google talk
		# we're still here.
		if time.time()-last_ping>120: # every 2 minutes
			# Say we're online.
			p = jabber.Presence()
			p.setFrom(JID)
			con.send(p)
			sendpresence(conf.general['status'])
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
				if conf.general.debug > 1:
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
