# $Id: fieldDescriptions.py,v 1.3 2004/06/09 09:23:46 ods Exp $
from qps import qFieldTypes as FT


fields = FT.FieldDescriptionsRepository({

    '*rubrics*': [
        ('id',      FT.STRING_ID()),
        ('title',   FT.STRING(title='Title',
                              indexPermissions=[('all', 'r')])),
        ('docs',    FT.EXT_VIRTUAL_REFERENCE(
                              title='Documents',
                              templateStream='docs',
                              indexPermissions=[('all', 'r')])),
    ],

    'docs': [
        ('id',      FT.INTEGER_AUTO_ID()),
        ('rubric',  FT.FOREIGN_DROP(title='Rubric', stream='rubrics',
                                    extraOption='(no rubric)')),
        ('title',   FT.STRING(title='Title',
                              indexPermissions=[('all', 'r')])),
        ('body',    FT.TEXT(title='Body text')),
    ],

})
