# $Id: qHTTP.py,v 1.29 2004/03/16 15:48:21 ods Exp $

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
class UnicodeFieldStorage(cgi.FieldStorage):
    '''
    This class can take charset argument, if its not None
    getfirst and getlist methods return unicode strings instead of
    binary strings (except ascii strings)
    '''
    
    def __init__(*args, **kwargs):
        self = args[0]
        try:
            self._charset = kwargs['charset']
            del kwargs['charset']
        except KeyError:
            self._charset = None
        cgi.FieldStorage.__init__(*args, **kwargs)

    def _decode(self, text):
        '''This method decodes non-ascii strings with self._chatset'''

        try:
            text.decode('ascii')
        except UnicodeError: # UnicodeDecodeError
            text = text.decode(self._charset)
        return text
    
    def getfirst(self, key, default=None):
        value = cgi.FieldStorage.getfirst(self, key, default)
        
        if self._charset:
            if type(value) is str: # it can be unicode because of default
                value = self._decode(value)
        return value

    def getlist(self, key):
        list = cgi.FieldStorage.getlist(self, key)
        result = []
        
        if self._charset:
            for value in list:
                if type(value) is str:
                    result.append(self._decode(value))
        else:
            result = list
        return result

class Form(object):
    '''Hacked cgi.FieldStorage for use with PPA HTTP adapters'''
    __cache = WeakKeyDictionary()
    _formClass = UnicodeFieldStorage

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
