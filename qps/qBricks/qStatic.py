# $Id: qStatic.py,v 1.2 2004/06/08 15:32:22 ods Exp $

'''Classes for hardcoded bricks'''

from qps import qFieldTypes
import qBase


class StaticItem(qBase.Item):

    def exists(self, ignoreStatus=0):
        return 1

    def store(self, names=None):
        self.storeExtFields(names)


class StaticStream(qBase.Stream):
    '''Base class for statically (in code) defined streams. For example:

        class Regions(StaticStream):
            itemListSpec = [
                {'id': 'moscow', 'title': 'Moscow'},
                {'id': 'peterburg', 'title': 'Saint-Peterburg'}]
    '''

    itemClass = StaticItem
    itemListSpec = []
    tableName = None

    def retrieve(self, ignoreStatus=0):
        if not self._retrieved or ignoreStatus:
            self.itemList = items = []
            for fields in self.itemListSpec:
                # XXX createItemFromCode? It will be usefull for ZODB-like
                # storages too.
                item = self.createNewItem(fields['id'])
                for field_name, value in fields.iteritems():
                    if field_name!='id':
                        item.initFieldFromCode(field_name, value)
                item.retrieveExtFields()
                item._retrieved = 1
                items.append(item)
            self._retrieved = 1

    def retrieveItem(self, item_id):
        self.retrieve()
        return self.getItem(item_id)

    def deleteItems(self, item_ids):
        pass

    def clear(self):
        pass

    def countItems(self, ignoreStatus=0):
        return len(self)

# vim: ts=8 sts=4 sw=4 ai et
