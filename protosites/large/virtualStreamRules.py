from qps.qUtils import DictRecord
from qps.qVirtual import VirtualRule
from qps.qSecurity import perm_all, perm_read, perm_list, perm_edit, \
     perm_delete
from streamDescriptions import Maker

virtualStreamRules = [
    VirtualRule(
        templateStream='documents',
        paramStream='rubrics',
        paramName='rubric',
        prefix='docs/rubrics',
        titleTemplate=u'%(rubric.title)s',
        streamParams=\
            DictRecord(
                permissions=[('docs', perm_all)],
                streamMakers=['TOCMaker', 'Maker', 'ItemsMaker'],
                itemMakers=['Maker'],
                order="num, date DESC",
                )
        ),
    ]
