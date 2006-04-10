# $Id: qSecurity.py,v 1.13 2005/11/30 22:44:36 corva Exp $

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

class BasicAuthHandler:
    securityGroupTable = {}
    authenticationHeader = 'Basic realm="QPS"'
    
    def getUser(self, request, response):
        return PyUser(request.user(), self.securityGroupTable)

    def cmd_notAuthorized(self, request, response, form, objs, user):
        raise self.ClientError(403, self.view_denied_error)

    def do_reAuth(self, request, response, form, objs, user):
        prev_user = form.getfirst('user')
        if prev_user==user.login:
            response.headers['WWW-Authenticate'] = self.authenticationHeader
            self.log(user, 'reAuth')
            raise self.ClientError(401, 'Authorization Required')
        else:
            raise self.SeeOther(self.prefix+objs[-1].path())
        
class CookieAuthHandler:
    usersStream = None # name of users stream
    authCookieName = "qpsuser" # name for auth cookie
    expireTimeout = 31536000 # year in seconds
    
    def authCookiePath(self):
        return self.prefix
    authCookiePath = qUtils.CachedAttribute(authCookiePath)

    def getUser(self, request, response):
        cookie = qHTTP.getCookie(request, self.authCookieName)
        try:
            login, passwd = cookie.split(':')
        except (ValueError, TypeError, AttributeError):
            login = None

        stream = self.site.retrieveStream(self.usersStream)

        if login is not None:
            user = stream.getUser(login)
            if user and getattr(user, user.stream.passwdField) == passwd:
                return user
        return stream.getUser(None)

    def cmd_notAuthorized(self, request, response, form, objs, user):
        login, passwd, perm_login = [form.getfirst(name) for name in \
                                     ('login', 'passwd', 'perm_login')]
        # crypt method used below only supports string types
        try:
            passwd = str(passwd)
        except UnicodeEncodeError:
            passwd = None        

        obj = objs[-1] or self.site
        if not (login and passwd):
            template = self.renderHelperClass(self, user)
            response.setContentType('text/html',
                                    charset=self.getClientCharset(request))
            response.write(template('login', brick=obj))
            raise self.EndOfRequest()
        else:
            stream = self.site.retrieveStream(self.usersStream)
            user = stream.getUser(login)
            if user and user.fields[stream.passwdField].crypt(passwd) == \
               getattr(user, stream.passwdField):
                expires = perm_login and self.expireTimeout or None
                qHTTP.setCookie(response, self.authCookieName,
                                "%s:%s" % (getattr(user, stream.loginField),
                                           getattr(user, stream.passwdField)),
                                expires, path=self.authCookiePath)
            # lets check if new user has perms to access path it requested
            try:
                required_permission, error = \
                                     self.required_object_permission[obj.type]
            except KeyError:
                raise RuntimeError('Object of unexpected type %r' % obj.type)
            else:
                if required_permission and \
                    not user.checkPermission(required_permission,
                                             obj.permissions):
                    obj = self.site
            self.log(user, "login", {'perm_login': perm_login})
            raise self.SeeOther(self.prefix+obj.path())

    def do_reAuth(self, request, response, form, objs, user):
        qHTTP.expireCookie(response, self.authCookieName,
                           path=self.authCookiePath)
        self.log(user, 'reAuth')
        raise self.SeeOther(self.prefix+objs[-1].path())


# vim: ts=8 sts=4 sw=4 ai et
