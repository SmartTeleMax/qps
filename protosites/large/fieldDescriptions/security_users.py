import FieldTypes as FT

itemFieldsOrder = ['login', 'passwd', 'title', 'security_groups']
itemFields = {
    'title': FT.STRING(title=u"Name",
                       indexPermissions=[('all', 'r')]),
    'login': FT.STRING(title=u"Login",
                       indexPermissions=[('all', 'r')]),
    'passwd': FT.DIGESTPASSWORD(title=u'Password', minlength=2),
    'security_groups': FT.FOREIGN_MULTISELECT(title=u"Groups",
                                              stream="security_groups",
                                              ),
    }
