import FieldTypes as FT

itemFieldsOrder = ['title']
itemFields = {
    'title': FT.STRING(title=u"Name",
                       indexPermissions=[('all', 'r')]),
    }
