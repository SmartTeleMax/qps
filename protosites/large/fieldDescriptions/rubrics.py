import FieldTypes as FT

fields = FT.FieldDescriptions([
    ('title', FT.STRING(title=u"Title",
                        indexPermissions=[('all', 'r')])),
    ('documents', FT.EXT_VIRTUAL_REFERENCE(
                      title=u"Documents",
                      templateStream="documents",
                      indexPermissions=[('all', 'r')],
                      )),
    ])
