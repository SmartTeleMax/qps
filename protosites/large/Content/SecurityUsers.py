import qps.qSecurity, qps.qUtils
import Content

class AnonymousUser(qps.qSecurity.UserBase):
    id = None
    groups = ['anonymous']
    login = 'anonymous'

    def __nonzero__(self):
        return 0

class SecurityUser(Content.Item, qps.qSecurity.UserBase):
    def groups(self):
        return [x.id for x in self.security_groups]
    groups = qps.qUtils.CachedAttribute(groups)

class SecurityUsers(qps.qSecurity.UsersStream):
    itemClass = SecurityUser
