import FieldTypes as FT

fields = FT.FieldDescriptions([
    ('login', FT.STRING(title=u"Login",
                        indexPermissions=[('all', 'r')])),
    ('passwd', FT.DIGESTPASSWORD(title=u'Password', minlength=2)),
    ('title', FT.STRING(title=u"Name",
                        indexPermissions=[('all', 'r')])),
    ('security_groups', FT.FOREIGN_MULTISELECT(title=u"Groups",
                                               stream="security_groups",
                                               )),
    ])
