# $Id: qHTTP.py,v 1.3 2005/06/01 23:41:12 corva Exp $

'''HTTP-related functions'''

from weakref import WeakKeyDictionary

def getCookie(request, name):
    import Cookie

    try:
        cookies = request.headers['Cookie']
    except KeyError:
        cookies = ''

    cookies = Cookie.SimpleCookie(cookies)
    if name in cookies:
        return cookies[name].value

def setCookie(response, name, value, expires=None, path=None, domain=None,
              max_age=None):
    import Cookie
    cookie = Cookie.SimpleCookie()
    cookie[name] = value
    morsel = cookie[name]

    if expires or path:
       if expires is not None:
         morsel["expires"] = expires
       if path is not None:
         morsel["path"] = path
       if domain is not None:
         morsel["domain"] = domain
       if max_age is not None:
         morsel["max-age"] = max_age

    name, value = morsel.output().split(': ')
    response.headers.add(name, value)

def expireCookie(response, name, expires=None, path=None, domain=None,
                 max_age=0):
   setCookie(response, name, "", expires, path, domain, max_age)

def getAdapter():
    '''Automagically determine adapter to be used.  Supports pure CGI and
    mod_python only.'''
    try:
        import _apache
    except ImportError:
        from PPA.HTTP.CGI import Adapter
    else:
        from PPA.HTTP.ModPython import Adapter
    return Adapter


import cgi
class FieldStorage(cgi.FieldStorage):
    '''
    This class can take charset argument, if its not None
    getfirst and getlist methods return unicode strings instead of
    binary strings (except ascii strings)
    '''
    
    def __init__(self, *args, **kwargs):
        self._charset = kwargs.pop('charset', None)
        self._errors = kwargs.pop('errors', 'strict')
        cgi.FieldStorage.__init__(self, *args, **kwargs)
        
    def getString(self, key, default=None):
        '''Like of getfirst, returning unicode object if charset is set'''
        value = self.getfirst(key)
        if value is None:
            return default
        elif self._charset:
            return value.decode(self._charset, self._errors)
        return value

    def getStringList(self, key):
        '''Like getlist, returning unicode objects if charset is set'''
        value = self.getlist(self, key)
        if self._charset:
            return [item.decode(self._charset, self._errors) for item in value]
        return value

    def initFields(self, site, fields):
        """Inits fields from form and returns a tuple of (item, errors)"""

        import qSecurity, qFieldTypes

        if not isinstance(fields, qFieldTypes.FieldDescriptions):
            fields = qFieldTypes.FieldDescriptions(fields)
        stream = site.createAnonStream(
            site.defaultStreamConf, streamClass="qps.qBricks.qBase.Stream",
            fields=fields,
            permissions=[('all', qSecurity.perm_all)])
        item = stream.createNewItem()
        errors = item.initFieldsFromForm(self)
        return (item, errors)
    

class Form(object):
    '''Hacked cgi.FieldStorage for use with PPA HTTP adapters'''
    __cache = WeakKeyDictionary()
    _formClass = FieldStorage

    def __new__(cls, request, charset=None):
        try:
            return cls.__cache[request]
        except KeyError:
            env = {'QUERY_STRING'   : request.query(),
                   'REQUEST_METHOD' : request.method()}
            hs = request.headers
            if hs.has_key('content-type'):
                env['CONTENT_TYPE'] = hs['content-type']
            if hs.has_key('content-length'):
                env['CONTENT_LENGTH'] = hs['content-length']
            cls.__cache[request] = form = cls._formClass(fp=request,
                                                         environ=env,
                                                         charset=charset)
            return form


# vim: ts=8 sts=4 sw=4 ai et
