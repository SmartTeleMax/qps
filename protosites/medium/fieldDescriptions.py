# $Id: fieldDescriptions.py,v 1.2 2004/06/04 11:46:40 ods Exp $
from qps import qFieldTypes as FT


defaultItemIDField = FT.INTEGER_AUTO_ID()

itemIDFields = {
    '*rubrics*' : FT.STRING_ID(),
}

itemFieldsOrder = {
    '*rubrics*' : ['title', 'docs'],
    'docs'      : ['rubric', 'title', 'body'],
}


itemFields = {

    '*rubrics*': {
        'title' : FT.STRING(title='Title',
                            indexPermissions=[('all', 'r')]),
    },

    'docs': {
        'rubric': FT.FOREIGN_DROP(title='Rubric', stream='rubrics',
                                  extraOption='(no rubric)'),
        'title' : FT.STRING(title='Title',
                            indexPermissions=[('all', 'r')]),
        'body'  : FT.TEXT(title='Body text'),
    },

}

itemExtFields={

    '*rubrics*': {
        'docs'  : FT.EXT_VIRTUAL_REFERENCE(
                                title='Documents',
                                templateStream='docs',
                                indexPermissions=[('all', 'r')]),
    },

}
