#   Programmer: limodou
#   E-mail:     limodou@gmail.com
#
#   Copyleft 2005 limodou
#
#   Distributed under the terms of the GPL (GNU Public License)
#
#   NewEdit is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
#   $Id: i18n.py 19 2005-09-10 15:37:08Z limodou $

import gettext
import glob
import os.path
import locale
import codecs

class _DUMY_CLASS:pass

class I18n(object):

    def __init__(self, domain, path):

        self.translation ={}
        self.lang = ''
        self.domain = domain

        mos = glob.glob(os.path.join(path, '%s*.mo' % domain))
        for filename in mos:
            f = os.path.splitext(os.path.basename(filename))[0]
            if f.startswith(domain + '_'):
                lang = f.split('_', 1)[1]
                self.translation[lang] = obj = _DUMY_CLASS()
                obj.mofile = os.path.normpath(filename)
                obj.transobj = None

    def install(self, lang):
        if self.translation.has_key(lang):
            if not self.translation[lang].transobj:
                self.translation[lang].transobj = obj = gettext.GNUTranslations(file(self.translation[lang].mofile, 'rb'))
            func = self.translation[lang].transobj.ugettext
        else:
            obj = gettext.NullTranslations()
            func = obj.ugettext
        return func
    
class BasicTR(object):
    i18n = None
    defaultlang = None
    
    def init(i18n, defaultlang):
        BasicTR.i18n = i18n
        BasicTR.defaultlang = defaultlang
    init = staticmethod(init)
    
    def __init__(self, msg, lang=None):
        self.lang = lang
        self.func = None
        self.msg = None
        self.args = None
        self.nnodes = []
        self.pnodes = []
        self.setlang(self.lang)
        self.msg = msg
        
    def para(self, *args):
        self.args = args
        return self
        
    def __unicode__(self):
        return self.getvalue()
        
    def __str__(self):
        value = self.getvalue()
        if isinstance(value, unicode):
            try:
                return value.encode(locale.getdefaultlocale()[1])
            except:
                return value.encode('utf-8')
        else:
            return value
    
    def getvalue(self):
        if self.args:
            if len(self.args) == 1 and isinstance(self.args[0], dict):
                value = self.func(self.msg) % self.args[0]
            else:
                value = self.func(self.msg) % self.args
        else:
            value = self.func(self.msg)
        return ''.join(map(self._getvalue, self.pnodes)) + value + ''.join(map(self._getvalue, self.nnodes))
    
    def _getvalue(self, obj):
        if isinstance(obj, BasicTR):
            return unicode(obj)
        else:
            return obj
        
    def __repr__(self):
        return self.__str__()
    
    def __add__(self, obj):
        self.nnodes.append(obj)
        return self
        
    def __radd__(self, obj):
        self.pnodes.append(obj)
        return self
        
    def setlang(self, lang):
        self.lang = lang
        if not self.lang:
            lang = self.defaultlang
        else:
            lang = self.lang
        self.func = self.i18n.install(lang)
        for obj in self.pnodes:
            if isinstance(obj, BasicTR):
                obj.setlang(lang)
        for obj in self.nnodes:
            if isinstance(obj, BasicTR):
                obj.setlang(lang)
        
    def clear(self):
        self.lang = None
        self.setlang(self.lang)
        
    def encode(self, encoding):
        return self.getvalue().encode(encoding)
    
    def __getattr__(self, name):
        return getattr(self.getvalue(), name)
    
def install(domain, path, lang, func='_'):
    i18nobj = I18n(domain, path)
    BasicTR.init(i18nobj, lang)
    import __builtin__
    __builtin__.__dict__[func] = BasicTR
    
def isobj(msg):
    if isinstance(msg, BasicTR):
        return True
    else:
        return False
    
def Unicode(msg, encoding):
    if isobj(msg):
        return msg.getvalue()
    else:
        return unicode(msg, encoding)
    
def listlang():
    return BasicTR.i18n.translation.keys() + ['en']

if __name__ == '__main__':
    install('confbot', 'locale', 'zh_CN')
    
    #a = _('Success') + 'c' + _('%s is %s').para('1', '2') + 'aaa'
    a = _('You %s %s').para('1', '2')
    print a
    print Unicode(_('''Topic: %(topic)s
%(lastlog)s''').para({
			"topic" : 'topic',
			"lastlog" : "\n".join(['a']),
			}) + '\n---------------\n', 'gbk').encode('gbk')