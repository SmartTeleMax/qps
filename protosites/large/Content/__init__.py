from qps.qBricks.qSQL import SQLStream, SQLItem

# make server client

class ConnectError(Exception): pass

class MakeServerClient:
    def connect(self, path):
        import socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            sock.connect(path)
        except socket.error:
            logger.warning('Connect to make-server failed')
            raise ConnectError
        return sock

    def make(self, obj):
        try:
            sock = self.connect(obj.site.makeSock)
        except ConnectError:
            pass
        else:
            sock.send(obj.path())

# store handlers

class ItemStoreHandler(object, MakeServerClient):
    def handle(self, item, names=None):
        self.make(item)
        #item.stream.storeHandler.handle(item.stream)

    
class CircularItemStoreHandler(ItemStoreHandler):
    def old_handle(self, item, names=None, recursion=1):
        self.make(item)

        if recursion:
            for name in item.stream.allItemFields.keys():
                value = getattr(item, name)
            
                try:
                    value.storeHandler.handle(value, recursion=0)
                except AttributeError:
                    pass

                try:
                    for subvalue in value:
                        subvalue.storeHandler.handle(subvalue, recursion=0)
                except (TypeError, AttributeError):
                    pass

    def handle(self, item, names=None, recursion=1):
        self.make(item)

        if recursion:
            for name, field in item.stream.allItemFields.items():
                value = getattr(item, name)
                
                if field.handleStore and value:
                    if field.iterHandleStore:
                        for subvalue in value:
                            subvalue.storeHandler.handle(subvalue,
                                                         recursion=0)
                    else:
                        value.storeHandler.handle(value, recursion=0)
  

class StreamStoreHandler(object, MakeServerClient):
    def handle(self, stream, recursion=0):
        self.make(stream)
    

# bricks

class Item(SQLItem):
    storeHandler = CircularItemStoreHandler()
    
    def splitId(self):
        import re
        return '/'.join(re.findall('\d\d?', str(self.id)))

    def uscSplitId(self):
        splitted_id = self.splitId()
        if splitted_id != str(self.id):
            splitted_id = '_%s' % splitted_id.replace('/', '/_')
            return '%s/%s' % (splitted_id, self.id)
        else:
            return self.id


class Stream(SQLStream):
    itemClass = Item
    storeHandler = StreamStoreHandler()
