# $Id: $
from qps import qFieldTypes as FT


itemIDFields = {
    'docs'      : FT.INTEGER_AUTO_ID(),
}


itemFieldsOrder = {
    'rubrics'   : ['title', 'docs'],
    'docs'      : ['rubric', 'title', 'body'],
}


itemFields = {

    'rubrics': {
        'title' : FT.STRING(title='Title',
                            indexPermissions=[('all', 'r')]),
    },

    'docs': {
        'rubric': FT.FOREIGN_DROP(title='Rubric', stream='rubrics',
                                  extra_option='(no rubric)'),
        'title' : FT.STRING(title='Title',
                            indexPermissions=[('all', 'r')]),
        'body'  : FT.TEXT(title='Body text'),
    },

}

itemExtFields={

    'rubrics': {
        'docs'  : FT.EXT_VIRTUAL_REFERENCE(
                                title='Documents',
                                templateStream='docs',
                                indexPermissions=[('all', 'r')]),
        },
    },

}
