# $Id: qSecurity.py,v 1.22 2006/11/22 23:38:21 corva Exp $

'''Function to check permissions'''

import os, types, logging, qUtils, qHTTP
from qBricks.qSQL import SQLStream, SQLItem
from qDB.qSQL import Query, Param
logger = logging.getLogger(__name__)

# security table should be defined in local Cfg like following:
#   securityGroupTable = {
#       'wheel' : ['hwb', 'phd', 'sgt'],
#       'editor': ['moderator', 'strana']
#   }
#
# access rights for stream should be defined like following:
#   [('wheel', perm_all), ('editor', perm_edit)]
#
# Permissions:
# r - read (former 'view' for streams and 'read' for fields)
# w - write (former 'edit')
# x - list (analogy with UNIX permissions for directories)
# c - create (former 'add')
# d - delete

perm_all    = 'rwxcd'
perm_read   = 'rx'
perm_list   = 'x'
perm_edit   = 'rwx'
perm_delete = 'xd'

# security user is a class with the following methods:
# checkPermission(perm, perms_list) -> bool
# getPermissions(perm_list) -> perms string
#
# ...and attributes:
# login
# passwd (optional for auth schemas what authenticates users themselves)

defaultGroups = ['anonymous']

class UserBase:

    def __str__(self):
        return self.login

    def __nonzero__(self):
        return self.login is not None

    def checkPermission(self, perm, perms_list):
        groups = self.groups+['all']
        for group, perms in perms_list:
            if perm in perms and group in groups:
                return 1
        return 0

    def getPermissions(self, perms_list):
        groups = self.groups+['all']
        all_perms = []
        for group, perms in perms_list:
            if group in groups:
                for perm in perms:
                    if perm not in all_perms:
                        all_perms.append(perm)
        return ''.join(all_perms)


class PyUser(UserBase):
    '''Simple user class with hard-coded groups_table'''

    permissions = []

    def __init__(self, login, groups_table={}):
        self.login = login
        self.groups_table = groups_table

    def groups(self):
        groups = defaultGroups
        user = self.login
        for group, users in self.groups_table.items():
            if user in users:
                groups.append(group)
        return groups
    groups = qUtils.CachedAttribute(groups)


class UserItem(UserBase, SQLItem):
    """Basic class of Security User item stored in DB

    Groups determinations is very different, due to this
    groups attribute is set to default value.

    Groups determination must be implemented in derived classes,
    for example, if groups are stored as FOREIGN_MULTISELECT field qps_groups:

    def groups(self):
        return [x.id for x in self.qps_groups]
    groups = qUtils.CachedAttribute(groups)"""

    groups = defaultGroups # should be overloaded

    def __str__(self):
        return getattr(self, self.stream.loginField)

    def __nonzero__(self):
        return self.id is not None


class UsersStream(SQLStream):
    itemClass = UserItem
    loginField = "login"
    passwdField = "passwd"

    def getUser(self, login=None):
        if login:
            table, fields, condition, group, order = self.constructQuery()
            condition = self.dbConn.join(
                [condition, Query('%s=' % self.loginField, Param(login))])
            items = self.itemsByQuery(table, fields, condition, group=group)
            if items:
                return items[0]
        # return default "False" user
        return self.createNewItem()

    def getLogin(self, user):
        return getattr(user, self.loginField)

    def getPassword(self, user):
        return getattr(user, self.passwdField)

    def checkPassword(self, user, passwd):
        # crypt method used below only supports string types
        try:
            passwd = str(passwd)
        except UnicodeEncodeError:
            return False
        else:
            return bool(user.fields[self.passwdField].crypt(passwd) == \
                        self.getPassword(user))

# auth handler is a class mixed to Edit.Edit
# it have to define following methods:
#
# getUser(...)
#               - this method returns security user object described above
#                 or false value (this mean the request is being done by
#                 unauthenticated user (cmd_notAuthorized is called in this
#                 way)
# cmd_notAuthorized(...)
#               - handles requests by unathorazed users, can simply display
#               - 401 message or handle authentication process
# do_reAuth(...)
#               - logs current user out


class Authentication(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def getUser(self, publisher, request, response):
        "Returns user instance"
        raise NotImplementedError()

    def requestLogin(self, publisher, request, response, form):
        "Requests login from user"
        raise NotImplementedError()

    def login(self, publisher, request, response, form):
        "Sets response to log user in"
        raise NotImplementedError()

    def logout(self, publisher, request, respnse, form):
        "Sets response to log user out"
        raise NotImplementedError()


class HTTPAuthentication(Authentication):
    securityGroupTable = {}
    authenticationHeader = 'Basic realm="QPS"'

    def getUser(self, publisher, request, response):
        return PyUser(request.user(), self.securityGroupTable)

    def requestLogin(self, publisher, request, response, form):
        response.headers['WWW-Authenticate'] = self.authenticationHeader
        raise publisher.ClientError(401, 'Authorization Required')


class AbstractCookieAuthentication(Authentication):
    """Implements HTTP Cookie authentication.

    cookieName - name of HTTP cookie header to be used for storing auth info
    cookiePathTmpl - qUtils.interpolateString template for cookie path. Context
                     is {'publisher': publisher} where publisher is Publisher's
                     instance, from where auth is used
    expireTimeout - expire timeout in seconds, is used if user choose to
                    login permanently

    NOTE: This class is not complete. It should be subclassed and methods

    authBySecret
    authByLogin
    checkSecret
    makeSecret

    Must be implemented in subclass. See docinfo for methods for more details.
    """

    cookieName = "qpsuser" # name for auth cookie header
    cookiePathTmpl = "%(publisher.prefix)s" # path for auth cookie header
    expireTimeout = 31536000 # year in seconds

    def _cookiePath(self, publisher):
        return qUtils.interpolateString(self.cookiePathTmpl,
                                        {'publisher': publisher})

    def getUser(self, publisher, request, response):
        """Authenticates user by HTTP-request"""

        cookie = qHTTP.getCookie(request, self.cookieName)
        try:
            login, secret = cookie.split(':')
        except (ValueError, TypeError, AttributeError):
            login = secret = None

        return self.authBySecret(publisher, request, login, secret)

    def login(self, publisher, request, response, form, permanent=False):
        login, passwd, perm_login = [form.getfirst(name) for name in \
                                     ('login', 'passwd', 'perm_login')]
        perm_login = permanent or perm_login

        user = self.authByLogin(publisher, login, passwd)
        if user:
            expires = perm_login and self.expireTimeout or None
            cookie = '%s:%s' % (user.stream.getLogin(user),
                                self.makeSecret(request, user))
            qHTTP.setCookie(response, self.cookieName,
                            cookie, expires,
                            path=self._cookiePath(publisher))
        return user

    def requestLogin(self, publisher, request, response, form, path):
        template = publisher.renderHelperClass(
            publisher, self.getUser(publisher, request, response))
        response.setContentType(
            'text/html', charset=publisher.getClientCharset(request))
        response.write(template('login', path=path))
        raise publisher.EndOfRequest()

    def logout(self, publisher, request, response, form):
        qHTTP.expireCookie(response, self.cookieName,
                           path=self._cookiePath(publisher))

    def authBySecret(self, publisher, request, login, secret):
        """Checks login and secret against user database.

        Returns user object, if user is not authenticated bool(user)
        must be False"""
        raise NotImplementedError()

    def authByLogin(self, publisher, login, passwd):
        """Checks login and password against user database.

        Returns user object, if user is not authenticated bool(user)
        must be False"""
        raise NotImplementedError()

    def checkSecret(self, request, user, secret):
        """Return True if secret corresponds to request and user, and False
        if it doesnt"""
        raise NotImplementedError()

    def makeSecret(self, request, user):
        """Return secret string to be used for authentication"""
        raise NotImplementedError()


class CookieAuthentication(AbstractCookieAuthentication):
    """Implements AbstractCookieAuthentication, uses UsersStream as
    users database.

    Attribute 'usersStream' must contain name of stream, which streamClass
    is inherited from UsersStream.

    Example usage:

    auth = CookieAuthentication(usersStream='customers')
    """

    def __init__(self, usersStream="users", **kwargs):
        self.usersStream = usersStream
        super(CookieAuthentication, self).__init__(**kwargs)

    def authBySecret(self, publisher, request, login, secret):
        stream = publisher.site.retrieveStream(self.usersStream)
        if login is not None:
            user = stream.getUser(login)
            if user and self.checkSecret(request, user, secret):
                return user
        return stream.getUser(None)

    def authByLogin(self, publisher, login, passwd):
        stream = publisher.site.retrieveStream(self.usersStream)
        user = stream.getUser(login)
        if user and stream.checkPassword(user, passwd):
            return user
        else:
            return stream.getUser(None)

    # for compatibility with previous changeset only
    # please drop if it's unused
    checkCreds = authByLogin

    def checkSecret(self, request, user, secret):
        return user.stream.getPassword(user) == secret

    def makeSecret(self, request, user):
        return user.stream.getPassword(user)

# vim: ts=8 sts=4 sw=4 ai et
