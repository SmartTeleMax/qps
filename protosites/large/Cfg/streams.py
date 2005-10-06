from qps.qUtils import DictRecord, Descriptions
from qps.qSecurity import perm_all, perm_read, perm_list, perm_edit, \
     perm_delete
import Content

class Maker(list):
    def __init__(self, *args, **kwargs):
        list.__init__(self)
        for arg in args: self.append(arg)
        self.append(kwargs)

streamDescriptions = Descriptions([
    ('qps_users',
     DictRecord(title=u"������������",
                tableName="qps_users",
                streamClass="qps.qSecurity.UsersStream",
                modifiers=[qpsUserGroups, qpsUserPermissions],
                permissions=[('wheel', perm_all)],
                fields=FT.FieldDescriptions([
                    ('id', FT.INTEGER_AUTO_ID()),
                    ('login', FT.STRING(title=u"�����",
                                        indexPermissions=[('all', 'r')])),
                    ('passwd',  FT.DIGESTPASSWORD(title=u'������',
                                                  minlength=2)),
                    ('qps_groups', FT.EXT_FOREIGN_MULTISELECT(
                                       title=u"������ �������",
                                       stream="qps_groups",
                                       tableName="qps_users_groups",
                                       valueFieldName="agroup",
                                       indexPermissions=[('all', 'rw')]
                                       )),
                    ])
                )),
    ('qps_groups',
     DictRecord(title=u"������ �������������",
                tableName="qps_groups",
                templateCat="qps_groups",
                streamClass="Bricks.Stream",
                permissions=[('wheel', perm_all)],
                fields=FT.FieldDescriptions([
                    ('id', FT.STRING_ID()),
                    ('title', FT.STRING(title=u"��������",
                                        indexPermissions=[('all', 'r')])),
                    ]),
                ))
    ])

virtualStreamRules = []
