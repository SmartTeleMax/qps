# $Id: qStatic.py,v 1.4 2004/03/16 15:56:20 ods Exp $

'''Classes for hardcoded bricks'''

from qps import qFieldTypes
import qBase


class DefaultItemFields(dict):
    '''Dictionary-like object with STRING value for any key'''
    def __getitem__(self, field_name):
        return self.get(field_name, qFieldTypes.STRING)


class StaticItem(qBase.Item):

    def exists(self, ignoreStatus=0):
        return 1

    def store(self, names=None):
        self.storeExtFields(names)


class StaticStream(qBase.Stream):
    '''Base class for statically (in code) defined streams. For example:

        class Regions(ListStream):
            itemListSpec = [
                ('moscow',          {'title': 'Moscow'}),
                ('peterburg',       {'title': 'Saint-Peterburg'})]
    '''

    itemClass = StaticItem
    itemListSpec = []
    tableName = None
    itemFields = DefaultItemFields()

    def retrieve(self, ignoreStatus=0):
        if not self._retrieved:
            map(self.addItem, self.itemListSpec)
            self._retrieved = 1

    def retrieveItem(self, item_id):
        self.retrieve()
        return self.getItem(item_id)

    def deleteItems(self, item_ids):
        pass

    def clear(self):
        pass

    def addItem(self, (id, init_values)):
        item = self.itemClass(self.site, self, id)
        item.__dict__.update(init_values)
        item.retrieveExtFields()
        item._retrieved = 1
        self.itemList.append(item)

    def countItems(self, ignoreStatus=0):
        return len(self)

# vim: ts=8 sts=4 sw=4 ai et
