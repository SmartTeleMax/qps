# $Id: qStatic.py,v 1.4 2004/06/18 08:02:12 ods Exp $

'''Classes for hardcoded bricks'''

from qps import qFieldTypes
import qBase


class StaticItem(qBase.Item):

    def exists(self, ignoreStatus=0):
        return 1

    def store(self, names=None):
        self.storeExtFields(names)


class StaticStream(qBase.Stream):
    '''Class for streams with statically defined (hard-coded) items data.
    
    The simpiest way to use it is defining itemListSpec option in stream
    configuration.  But for large data sets you may want to subclass, e.g.:
        class Cities(StaticStream):
            itemListSpec = [
                {'id': 'moscow',    'title': 'Moscow'},
                {'id': 'peterburg', 'title': 'Saint-Peterburg'},
            ]
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
                        item.initFieldFrom('Code', field_name, value)
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
