from qps.qUtils import DictRecord
from qps.qSecurity import perm_all, perm_read, perm_list, perm_edit, \
     perm_delete
import Content

class Maker(list):
    def __init__(self, *args, **kwargs):
        list.__init__(self)
        for arg in args: self.append(arg)
        self.append(kwargs)

streamDescriptions = {
    'security_users': DictRecord(
        title=u"Security: users",
        tableName="security_users",
        streamCat="security_users",
        streamClass="Content.SecurityUsers.SecurityUsers",
        permissions=[('wheel', perm_all)],
        ),

    'security_groups': DictRecord(
        title=u"Security: groups",
        tableName="security_groups",
        streamCat="security_groups",
        streamClass="Content.Stream",
        permissions=[('wheel', perm_all)],
        ),
    
    'documents': DictRecord(
        title=u"Documents",
        tableName="documents",
        order="date DESC",
        indexNum=25,
        streamCat="documents",
        streamClass="Content.Stream",
        ),
    
    'rubrics': DictRecord(
        title=u"Rubrics",
        tableName="rubrics",
        streamCat="rubrics",
        streamClass="Content.Stream",
        permissions=[('docs', perm_all)],
        streamMakers=['ItemsMaker'],
        itemMakers=['VirtualsMaker']
        ),
    }
