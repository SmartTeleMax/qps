# $Id: qSQL.py,v 1.4 2004/06/08 15:32:22 ods Exp $

'''Classes for bricks with data stored in SQL DB'''

import logging
logger = logging.getLogger(__name__)
import qBase
from qps import qUtils


class SQLItem(qBase.Item):
    def initFieldsFromDB(self, row):
        '''Initialize item fields from DB row'''
        fields = self.stream.indexFields
        for field_name, db_value in row.items():
            if fields.has_key(field_name):
                value = fields[field_name].convertFromDB(db_value, item=self)
                setattr(self, field_name, value)

    def prepareFieldsForDB(self):
        '''Reverse for initFieldsFromDB: return dictionary with current values
        of fields suitable to store in DB'''
        # XXX This code would be faster in place of use
        # another solution - adding optional field_names argument
        fields = {}
        for field_name, field_type in self.fields.iteritems():
            if field_type.storeControl!='never':
                fields[field_name] = field_type.convertToDB(
                    getattr(self, field_name),
                    self)
        return fields

    def prepareJoinFieldsForDB(self):
        fields = {}
        for field_name, field_type in self.stream.joinFields.items():
            if field_type.storeControl!='never':
                fields[field_name] = field_type.convertToDB(
                    getattr(self, field_name),
                    self)
        return fields

    def sqlCondition(self):
        '''Return SQL condition for this item'''
        return "%s.id=%s" % \
               (self.stream.tableName,
                self.dbConn.convert(
                    self.fields['id'].convertToDB(self.id, self)))

    def exists(self, ignoreStatus=0):
        '''Return True if item exists in DB and False otherwise'''
        if self.id is not None:
            # to cache results status variables _exists and _retrieved are used
            if self._exists is None and self._retrieved:
                self._exists = 1
            if self._exists is None or ignoreStatus:
                self._exists = self.dbConn.selectField(self.stream.tableName,
                                        'COUNT(*)', self.sqlCondition())
            return self._exists
        else:
            return 0

    def existsInStream(self):
        '''Return True if item exists and belong to self.stream in DB, False
        otherwise'''
        table, fields, condition, group = self.stream.constructQuery()
        if group:
            fields = 'DISTINCT %s' % group
        elif fields[0][:len('DISTINCT')].upper()=='DISTINCT':
            fields = ','.join(fields)
        else:
            fields = '*'
        condition = self.dbConn.join([condition, self.sqlCondition()])
        return self.dbConn.selectField(table, 'COUNT(%s)' % fields, condition)

    def retrieve(self, ignoreStatus=0):
        '''Retrieve data of item from DB'''
        if not self._retrieved or ignoreStatus:
            table, fields, condition, group = self.stream.constructQuery()
            condition = self.dbConn.join([condition, self.sqlCondition()])
            rows = self.dbConn.selectRowsAsDict(table,
                        fields, condition=condition, group=group)
            if len(rows)==1:
                row = rows[0]
                self.initFieldsFromDB(row)
                self._retrieved = 1
                self.retrieveExtFields()
            elif rows:
                raise RuntimeError('There are %s rows for single item' % \
                                                                   len(rows))
            else:
                # XXX raise exception?
                self._retrieved = 0
        # XXX returned value is nowhere used. if we use exception for error
        # then return nothing
        return self._retrieved

    def store(self, names=None):
        '''Store data of item (new or existing) in DB'''
        fields = self.prepareFieldsForDB()
        join_fields = self.prepareJoinFieldsForDB()
        # remove from fields read-only fields
        for field_name in fields.keys():
            field_type = self.stream.indexFields[field_name]
            if field_type.storeControl=='never' or \
                    (field_type.storeControl!='always' and \
                     names is not None and field_name not in names):
                del fields[field_name]
        tnx = self.dbConn.getTransaction()
        if not self.exists(1):
            # INSERT
            if not (self.stream.itemIDField.omitForNew and self.id is None):
                fields['id'] = self.stream.itemIDField.convertToDB(self.id,
                                                                   self)
            cursor = self.dbConn.insert(self.stream.tableName, fields)

            if self.stream.itemIDField.omitForNew and self.id is None:
                # Auto-increment support
                self.id = self.stream.itemIDField.convertFromDB(
                        self.dbConn.lastInsertID(self.stream.tableName, 'id'),
                        self)
            self._exists = 1
        elif fields:
            # UPDATE
            cursor = self.dbConn.update(self.stream.tableName, fields,
                                        self.sqlCondition())
        if join_fields:
            param_value = getattr(self.stream, self.stream.virtual.paramName)
            join_field_type = self.fields[self.stream.joinField]
            param_db_value = join_field_type.itemField.convertToDB(param_value,
                                                                   self)
            id_db_value = self.stream.itemIDField.convertToDB(self.id, self)
            condition = '%s=%s AND %s=%s' % (
                                    join_field_type.idFieldName,
                                    self.dbConn.convert(id_db_value),
                                    self.stream.virtual.paramName,
                                    self.dbConn.convert(param_db_value))
            self.dbConn.update(self.stream.joinTable, join_fields, condition)
        self.storeExtFields(names)
        tnx.close()
        # XXX should handler be called insude transaction?
        # XXX May be just call inherited store?
        self.stream.storeHandler.handleItemStore(self, names)
        
    def delete(self):
        '''Delete item from DB'''
        self.stream.deleteItems([self.id])


class SQLStream(qBase.Stream):
    itemClass = SQLItem
    
    def calculateLimits(self):
        '''Return limits for items retrieval (offset and number)'''
        if self.indexNum>0 and self.page>0:
            limits=[self.indexNum*(self.page-1), self.indexNum]
        else:
            # self.dbConn.select* methods ignore zero limits
            limits=[0,0]
        return limits

    def addToCondition(self, new_cond, op="AND"):
        if new_cond:
            if self.condition:
                self.condition = '(%s) %s (%s)' % (self.condition, op, new_cond)
            else:
                self.condition = new_cond

    def createItemFromDB(self, db_row):
        # For internal use: create item from dictionary of fields
        id = self.fields['id'].convertFromDB(db_row['id'], self)
        del db_row['id']
        item = self.itemClass(self.site, self, id)
        item.initFieldsFromDB(db_row)
        item._retrieved = 1
        item.retrieveExtFields()
        return item

    def constructQuery(self):
        '''Return parts of query to retrieve stream items. Can be overriden in
        child class.'''
        table = self.tableName
        fields = ["%s.%s" % (table, f) for f in self.fields.main.keys()]
        condition = self.condition
        group = self.group
        if hasattr(self, 'joinTemplate'):
            table = qUtils.interpolateString(self.joinTemplate, {'brick': self})
            condition = self.dbConn.join([condition,
                                          getattr(self, 'joinCondition', '')])
            if self.joinFields:
                fields += ["%s.%s" % (self.joinTable, f) \
                           for f in self.joinFields.keys()]
        return table, fields, condition, self.group

    def retrieveItems(self, **kwargs):
        params = dict(zip(('table', 'fields', 'condition', 'group'),
                          self.constructQuery()))
        params.update(kwargs)
        return self.itemsByQuery(**params)

    def itemsByQuery(self, table, fields, condition='', order='', group='',
                     limitOffset=0, limitSize=0):
        rows = self.dbConn.selectRowsAsDict(table, fields, condition, order,
                                            group, limitOffset, limitSize)
        items = []
        for row in rows:
            items.append(self.createItemFromDB(row))
        return items

    def retrieve(self, ignoreStatus=0):
        '''Retrieve stream items'''
        if not self._retrieved or ignoreStatus:
            self.clear()
            logger.debug("Retrieving stream `%s'", self.id)
            limits=self.calculateLimits()
            table, fields, condition, group = self.constructQuery()
            self.itemList = self.itemsByQuery(table, fields, condition,
                  self.order, group, limitOffset=limits[0], limitSize=limits[1])
            self._retrieved = 1
        return self._retrieved

    def countItems(self, ignoreStatus=0):
        if not hasattr(self, '_count_items') or ignoreStatus:
            if self._retrieved and (self.indexNum==0 or \
                                    (self.page==1 and \
                                     self.indexNum>len(self.itemList)
                                     )
                                    ):
                self._count_items = len(self.itemList)
            else:
                table, fields, condition, group = self.constructQuery()
                if group:
                    fields = 'DISTINCT %s' % group
                elif fields[0][:len('DISTINCT')].upper()=='DISTINCT':
                    fields = ','.join(fields)
                else:
                    fields = '*'
                self._count_items = self.dbConn.selectField(table,
                                        'COUNT(%s)' % fields, condition)
        return self._count_items

    def deleteItems(self, item_ids):
        '''Delete several items from DB'''
        number_of_deleted = 0
        if item_ids:
            tnx = self.dbConn.getTransaction()
            if self.condition:
                # filter items existing in this stream (not it's table)
                table, fields, condition, group = self.constructQuery()
                item_ids = self.dbConn.selectFieldAsList(
                    table,
                    fields[0],
                    "(%s) AND (%s)" % (condition,
                                       self.dbConn.IN(fields[0], item_ids)))
            if item_ids:
                self.deleteExtFields(item_ids)
                cursor = self.dbConn.delete(
                    self.tableName,
                    self.dbConn.IN('id', item_ids))
                number_of_deleted = cursor.rowcount
            tnx.close()
            self.storeHandler.handleItemsDelete(self, items_ids)
        return number_of_deleted

# vim: ts=8 sts=4 sw=4 ai et
