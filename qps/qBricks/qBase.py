'''Base brick classes'''

import logging
logger = logging.getLogger(__name__)
from qps import qUtils, qEvents

class OrderAttribute(object):
    """Proxy for access to stream 'order' attribute. Normalizes order on set"""

    def __set__(self, inst, value):
        if not value:
            inst._order = ()
        else:
            inst._order = tuple(self._normalize(value))

    def __get__(self, inst, cls):
        return inst._order

    def _normalize(self, order):
        for name, direction in order:
            try:
                direction = direction.upper()
            except AttributeError:
                direction = None
            if direction not in ('ASC', 'DESC'):
                raise TypeError(
                    "Order direction should be a string 'asc' or 'desc'")
            yield name, direction

class Brick(object):
    '''Base class for all bricks (streams and items) with data stored in DB'''

    # cached status parameters
    _exists = None
    _retrieved = 0
    type = None

    def __init__(self, site, id=None):
        '''site      - site object collection almost all configuration
           id        - id of object (same as stream_id for stream.'''
        self.id = id
        self.site = qUtils.createWeakProxy(site)
        self.dbConn = site.dbConn

    def path(self):
        '''Return common path of object'''
        raise NotImplementedError()


class Item(Brick):
    '''Base class for items'''

    type = 'item'
    _ext_fields_retrieved = 0

    def __init__(self, site, stream, id, modifiers=[]):
        '''site      - see Brick
           stream    - stream in which this item is defined
           id        - item id
           dbValues  - optional initial values '''
        Brick.__init__(self, site, id)
        # XXX A bit ugly, but there is no better solution now.  Looking forward
        # callback argument of weakref.proxy().
        if stream.tag is None:
            self.stream = qUtils.createWeakProxy(stream)
        else:
            self.stream = stream
        self.permissions = stream.permissions
        for modifier in modifiers:
            modifier(self)

    def fields(self):
        return self.stream.fields
    fields = qUtils.CachedAttribute(fields)

    def indexFields(self):
        return self.stream.indexFields
    indexFields = qUtils.CachedAttribute(indexFields)

    def __eq__(self, other):
        # Note that the same objects taken from different streams are not
        # equal!
        if self is other:
            return 1
        elif self.__class__ is other.__class__:
            return self.stream==other.stream and self.id==other.id
        else:
            return NotImplemented

    def __ne__(self, other):
        return not (self==other)

    def path(self):
        return '%s%s.html' % (self.stream.path(),
                              self.fields.id.convertToString(self.id, self))

    def initFieldFrom(self, source, field_name, value):
        """Initializes brick's field

        source     - identifier of source. Code, DB, Form, String are known
                     sources
        field_name - name of field
        value      - field value in form of source"""

        field_type = self.indexFields[field_name]
        method = getattr(field_type, 'convertFrom%s' % source)
        setattr(self, field_name, method(value, self))

    def initFieldsFromForm(self, form, names=None):
        '''Initialize item fields from data in form.  Return dictionary
        {field_name: error_message, ...} (empty if initialization is
        successful).'''
        errors = {}
        if names is None:
            names = self.fields.keys()
        for field_name in names:
            if field_name!=self.fields.idFieldName:
                field_type = self.fields[field_name]
                if field_type.initFromForm:
                    try:
                        value = field_type.convertFromForm(form, field_name,
                                                           self)
                    except field_type.InvalidFieldContent, exc:
                        errors[field_name] = exc.message
                    else:
                        setattr(self, field_name, value)
        return errors

    def make(self, maker=None, maker_params={}):
        if maker is None:
            makers = [self.site.getMaker(desc, maker_params)
                      for desc in self.stream.itemMakers]
        else:
            makers = [maker]
        for maker in makers:
            maker.process(self)

    def makeAction(self):
        return self.stream.itemMakeAction(self)

    def virtualStreams(self):
        result = []
        for rule in self.stream.virtualRules:
            stream_id = rule.constructId(self)
            stream = self.site.retrieveStream(stream_id,
                                    tag=self.site.transmitTag(self.stream.tag))
            result.append(stream)
        return result
    virtualStreams = qUtils.CachedAttribute(virtualStreams)

    # --- Storage dependent methods (interface only) ---
    def exists(self, ignoreStatus=0):
        '''Return True if item exists and False otherwise'''
        raise NotImplementedError()

    def existsInStream(self):
        '''Return True if item exists and belong to self.stream, False
        otherwise'''
        raise NotImplementedError()

    def retrieve(self, ignoreStatus=0):
        '''Retrieve data of item'''
        raise NotImplementedError()

    def store(self, names=None):
        '''Store data of item (new or existing)'''
        self.storeExtFields(names)
        self.stream.storeHandler.handleItemStore(self, names)

    def touch(self):
        '''Touch the item (i.e. mark as its updated and need to be remaked)'''
        raise NotImplementedError()

    def delete(self):
        '''Delete item from DB'''
        self.stream.deleteItems([self.id])

    # --- External fields ---
    def retrieveExtFields(self):
        if not self._ext_fields_retrieved:
            for field_name, field_type in self.fields.external.iteritems():
                value = field_type.retrieve(item=self)
                setattr(self, field_name, value)
            self._ext_fields_retrieved = 1

    def storeExtField(self, field_name):
        field_type = self.fields[field_name]
        field_type.store(getattr(self, field_name), item=self)

    def storeExtFields(self, names=None):
        '''For each external field store it, if its listed in names.  By
        default store all external fields.'''
        for field_name, field_type in self.fields.external.iteritems():
            if field_type.storeControl!='never' and \
                    (field_type.storeControl=='always' or \
                     names is None or field_name in names):
                self.storeExtField(field_name)

    def deleteExtFields(self):
        self.stream.deleteExtFields([self.id])


class Stream(Brick):
    '''Base class for streams'''

    type = 'stream'
    itemClass = Item
    storeHandler = qEvents.StoreHandler()
    order = OrderAttribute()
    fieldsContainerName = None # name of fields container in site.fields

    def __init__(self, site, id, page=0, modifiers=[], **kwargs):
        Brick.__init__(self, site, id)
        # order is property, __dict__.update doesn't match
        for key, value in kwargs.iteritems():
            setattr(self, key, value)
        # XXX Why page is checked here and not in PagedStreamLoader?  Anyway,
        # this check is incomplete.
        if page<1:
            page = 1
        self.page = page

        # the list of items
        self.itemList = []
        self.itemModifiers = []
        self.features = []
        for modifier in modifiers:
            modifier(self)
            self.features.append(modifier.__class__.__name__)

    def fields(self):
        return self.site.fields[self.fieldsContainerName]
    fields = qUtils.CachedAttribute(fields)

    def joinFields(self):
        import qps.qFieldTypes
        default = qps.qFieldTypes.FieldDescriptions([])
        if hasattr(self, 'joinTable'):
            return self.site.fields.get(self.joinTable, default).main
        else:
            return default
    joinFields = qUtils.CachedAttribute(joinFields)

    def __eq__(self, other):
        return self is other or \
                (self.__class__ is other.__class__ and \
                 self.site is other.site and self.id==other.id)

    def __ne__(self, other):
        return not (self==other)

    def __len__(self):
        '''Return number of loaded items in stream'''
        self.retrieve()
        return len(self.itemList)

    def __getitem__(self, i):
        self.retrieve()
        return self.itemList[i]

    def __getslice__(self, start, stop):
        self.retrieve()
        return self.itemList[max(0, start):max(0, stop)]

    def __iter__(self):
        self.retrieve()
        return iter(self.itemList)

    def indexFields(self):
        return self.fields + self.joinFields
    indexFields = qUtils.CachedAttribute(indexFields)

    def virtualRules(self):
        result = []
        for rule in self.site.virtualStreamRules:
            if rule.matchParamStream(self):
                result.append(rule)
        return result
    virtualRules = qUtils.CachedAttribute(virtualRules)

    def getItem(self, item_id):
        '''Return item with id item_id if it is in self.itemList'''

        # Use hash for better performance
        if not (hasattr(self, "itemDict") and
                len(self.itemDict)==len(self.itemList)):
            self.itemDict = itemDict = {}
            for item in self.itemList:
                itemDict[item.id] = item
        return self.itemDict.get(item_id, None)

    def retrieveItem(self, item_id):
        item = self.getItem(item_id)
        if item is None:
            if not hasattr(self, 'retrieveItemCache'):
                self.retrieveItemCache = {}
            if not self.retrieveItemCache.has_key(item_id):
                item = self.itemClass(self.site, self, item_id,
                                      self.itemModifiers)
                if item.retrieve()!=1:
                    item = None
                self.retrieveItemCache[item_id] = item
            return self.retrieveItemCache.get(item_id, None)
        return item

    def path(self):
        return '/%s/' % self.id

    def retrieve(self, ignoreStatus=0):
        '''Retrieve stream items'''
        raise NotImplementedError()

    def clear(self):
        '''Clear list of retrieved items to break circular references'''
        if hasattr(self, 'itemList'):
            del self.itemList[:]
        if hasattr(self, 'itemDict'):
            self.itemDict.clear()
        if hasattr(self, 'retrieveItemCache'):
            self.retrieveItemCache.clear()
        self._retrieved = 0  # reset status

    def getVirtualParamItem(self):
        "Returns a virtual param item"

        if hasattr(self, 'virtual'):
            param_item = getattr(self, self.virtual.paramName)
            return param_item

    def createNewItem(self, item_id=None, init_fields=True):
        item = self.itemClass(self.site, self, item_id, self.itemModifiers)
        if init_fields:
            defaults = self.brickDefaults
            if hasattr(self, 'virtual'):
                virtual_param_names = self.virtual.itemParamNames
            else:
                virtual_param_names = []
            for field_name, field_type in self.fields.iteritems():
                if field_name!='id':
                    if field_name in virtual_param_names:
                        value = getattr(self, field_name)
                    elif defaults.has_key(field_name):
                        value = field_type.convertFromCode(
                            defaults[field_name], item)
                    else:
                        value = field_type.getDefault(item)
                    setattr(item, field_name, value)
        return item

    def makeAction(self):
        if hasattr(self, 'virtual'):
            param_item = getattr(self, self.virtual.paramName)
            return param_item.makeAction()
        return 'make'

    def make(self, maker=None, maker_params={}):
        if maker is None:
            if self.itemMakers and not self.streamMakers:
                logger.warning('Empty streamMakers but filled itemMakers for '\
                               'stream %r', self.id)
            makers = [self.site.getMaker(desc, maker_params)
                      for desc in self.streamMakers]
        else:
            makers = [maker]
        if makers:
            logger.debug('Making stream %r', self.id)
            for maker in makers:
                maker.process(self)
        else:
            logger.debug("Stream %r hasn't any makers", self.id)

    # --- Storage dependent methods (interface only) ---
    def deleteItems(self, item_ids):
        raise NotImplementedError()

    def retrieve(self, ignoreStatus=0):
        raise NotImplementedError()

    def countItems(self, ignoreStatus=0):
        # XXX Use len(self) in base class?
        raise NotImplementedError()

    def countPages(self):
        if not self.indexNum:
            return 1
        count = divmod(self.countItems() + self.indexNum - 1, self.indexNum)[0]
        if not count:
            return 1
        return count

    # --- External fields ---
    def deleteExtFields(self, item_ids):
        for field_name, field_type in self.fields.external.iteritems():
            field_type.delete(item_ids, stream=self)

    # --- Order functions ---
    def isDefaultOrder(self):
        """Checks if current stream order is default"""
        default = self.site.createStream(self.id, tag=self.tag).order
        return (default == self.order)

    def getFieldOrder(self, field_name):
        """Returns default order direction for field, matched by field_name,
        if field doesn't allow order - returns None"""
        field_type = self.fields.get(field_name)
        if not field_type or not field_type.allowOrder:
            return None
        return field_type.defaultOrderDirection.upper()


# vim: ts=8 sts=4 sw=4 ai et
