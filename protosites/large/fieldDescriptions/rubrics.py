import FieldTypes as FT

itemFieldsOrder = ['title', 'documents']
itemFields = {
    'title': FT.STRING(title=u"Title",
                       indexPermissions=[('all', 'r')]),
    }
itemExtFields = {
    'documents': FT.EXT_VIRTUAL_REFERENCE(
                     title=u"Documents",
                     templateStream="documents",
                     indexPermissions=[('all', 'r')],
                     ),
    }
