# $Id: qSecurity.py,v 1.1.1.1 2004/03/18 15:17:17 ods Exp $

'''Function to check permissions'''

import os, types, logging, qUtils, qHTTP
from qBricks.qSQL import SQLStream, SQLItem
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
        groups = []
        user = self.login
        for group, users in self.groups_table.items():
            if user in users:
                groups.append(group)
        return groups
    groups = qUtils.CachedAttribute(groups)


class UserItem(SQLItem, UserBase): pass

class UsersStream(SQLStream):

    itemClass = UserItem

    def getUser(self, login):
        table, fields, condition, group = self.constructQuery()
        condition = self.dbConn.join([condition,
                                      'login=%s' % self.dbConn.convert(login)])
        items = self.itemsByQuery(table, fields, condition, group=group)
        if items:
            return items[0]

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
        from qSecurity import PyUser
        return PyUser(request.user(), self.securityGroupTable)

    def cmd_notAuthorized(self, request, response, form, objs, user):
        raise self.ClientError(403, self.view_denied_error)

    def do_reAuth(self, request, response, form, objs, user):
        prev_user = form.getfirst('user')
        if prev_user==user.login:
            response.headers['WWW-Authenticate'] = self.authenticationHeader
            raise self.ClientError(401, 'Authorization Required')
        else:
            raise self.SeeOther(self.prefix+objs[-1].path())
        
class CookieAuthHandler:
    usersStream = None # name of users stream
    authCookieName = "qpsuser" # name for auth cookie
    
    def authCookiePath(self):
        return self.prefix
    authCookiePath = qUtils.CachedAttribute(authCookiePath)

    def getUser(self, request, response):
        cookie = qHTTP.getCookie(request, self.authCookieName)
        try:
            login, passwd = cookie.split(':')
        except (ValueError, TypeError, AttributeError):
            return None
        else:
            stream = self.site.retrieveStream(self.usersStream)
            user = stream.getUser(login)
            # here we assume what passwd is stored in "passwd" field
            if user and user.passwd == passwd:
                return user

    def cmd_notAuthorized(self, request, response, form, objs, user):
        login, passwd, perm_login = [form.getfirst(name) for name in \
                                     ('login', 'passwd', 'perm_login')]

        if not login:
            if objs[-1]:
                path = objs[-1].path()
            else:
                path = '/'
            template = self.renderHelperClass(self, user)
            response.setContentType('text/html',
                                    charset=self.getClientCharset(request))
            response.write(template('login', brick=self.site, path=path))
            raise self.EndOfRequest()
        elif passwd:
            stream = self.site.retrieveStream(self.usersStream)
            user = stream.getUser(login)

            if user:
                passwd_field = user.stream.allItemFields['passwd']
                if passwd_field.crypt(passwd) == user.passwd:
                    # success!
                    if perm_login:
                        expires = 84600*365
                    else:
                        expires = None
                    
                    qHTTP.setCookie(response, self.authCookieName,
                                    "%s:%s" % (user.login, user.passwd),
                                    expires, path=self.authCookiePath)
            raise self.SeeOther(self.prefix+objs[-1].path())

    def do_reAuth(self, request, response, form, objs, user):
        qHTTP.expireCookie(response, self.authCookieName,
                           path=self.authCookiePath)
        raise self.SeeOther(self.prefix+objs[-1].path())


# vim: ts=8 sts=4 sw=4 ai et
