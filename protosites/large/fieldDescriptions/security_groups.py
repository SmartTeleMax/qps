import FieldTypes as FT

fields = FT.FieldDescriptions([
    ('title', FT.STRING(title=u"Name", indexPermissions=[('all', 'r')]))
    ])
