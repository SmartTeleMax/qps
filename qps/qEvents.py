# $Id: qEvents.py,v 1.1 2005/02/15 15:24:37 corva Exp $

'''Event handlers'''

class StoreHandler(object):
    "Base class for store handlers"

    def handleItemStore(self, item, fields):
        """Method is called after item was stored. Item is item object,
        fields is a list of stored fields names"""
        pass

    def handleItemsDelete(self, stream, items_ids):
        """Is called after group of items was deleted. Stream is instance of
        corresponding stream, items_ids is a list of deleted items ids"""
        pass


class MakeStoreHandler(StoreHandler):
    "Re-makes items and streams after store/delete actions"

    def make(self, obj, maker_params={}):
        from qPath import PathParser
        parser = PathParser(obj.site)
        obj = parser(obj.path())[-1]
        obj.make(maker_params=maker_params)

    def handleItemStore(self, item, fields):
        self.make(item)
        self.make(item.stream, {'skip_items': 1})

    def handleItemsDelete(self, stream, item_ids):
        self.make(stream, {'skip_items': 1})


