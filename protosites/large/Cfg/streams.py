# -*- coding: koi8-r -*-

from qps.qUtils import DictRecord, Descriptions
from qps.qSecurity import perm_all, perm_read, perm_list, perm_edit, \
     perm_delete

import Modifiers

qpsUserGroups = Modifiers.GroupsFeature(
    templates=[('id', 'qps_user-%(value)s')],
    collectionTemplates=[('qps_groups', '%(value.id)s')]
    )

qpsUserPermissions = Modifiers.ItemPermissionsFeature(
    templates=[('id', ('qps_user-%(value)s', 'rw'))]
    )

class Maker(list):
    def __init__(self, *args, **kwargs):
        list.__init__(self)
        for arg in args: self.append(arg)
        self.append(kwargs)

streamDescriptions = Descriptions([
    ('qps_users',
     DictRecord(title=u"Пользователи",
                tableName="qps_users",
                streamClass="qps.qSecurity.UsersStream",
                modifiers=[qpsUserGroups, qpsUserPermissions],
                permissions=[('wheel', perm_all)],
                fields=FT.FieldDescriptions([
                    ('id', FT.INTEGER_AUTO_ID()),
                    ('login', FT.STRING(title=u"Логин",
                                        indexPermissions=[('all', 'r')])),
                    ('passwd',  FT.DIGESTPASSWORD(title=u'Пароль',
                                                  minlength=2)),
                    ('qps_groups', FT.EXT_FOREIGN_MULTISELECT(
                                       title=u"Группы доступа",
                                       stream="qps_groups",
                                       tableName="qps_users_groups",
                                       valueFieldName="agroup",
                                       indexPermissions=[('all', 'rw')]
                                       )),
                    ])
                )),
    ('qps_groups',
     DictRecord(title=u"Группы пользователей",
                tableName="qps_groups",
                templateCat="qps_groups",
                streamClass="qps.qBricks.qSQL.SQLStream",
                permissions=[('wheel', perm_all)],
                fields=FT.FieldDescriptions([
                    ('id', FT.STRING_ID()),
                    ('title', FT.STRING(title=u"Название",
                                        indexPermissions=[('all', 'r')])),
                    ]),
                ))
    ])

virtualStreamRules = []
