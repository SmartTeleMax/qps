# $Id: qBase.py,v 1.8 2004/03/16 15:56:20 ods Exp $

'''Base brick classes'''

import weakref, logging
logger = logging.getLogger(__name__)
from qps import qUtils


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
        try:
            self.site = weakref.proxy(site)
        except TypeError:
            self.site = site
        self.dbConn = site.dbConn

    def path(self):
        '''Return common path of object'''
        raise NotImplementedError()


class Item(Brick):
    '''Base class for items'''

    type = 'item'
    _ext_fields_retrieved = 0

    def __init__(self, site, stream, id):
        '''site      - see Brick
           stream    - stream in which this item is defined
           id        - item id
           dbValues  - optional initial values '''
        Brick.__init__(self, site, id)
        # XXX A bit ugly, but there is no better solution now.  Looking forward
        # callback argument of weakref.proxy().
        if stream.tag is None:
            try:
                self.stream = weakref.proxy(stream)
            except TypeError:
                self.stream = stream
        else:
            self.stream = stream
        self.permissions = stream.permissions

    def __eq__(self, other):
        # Note that the same objects taken from different streams are not
        # equal!
        return self is other or \
                (self.__class__ is other.__class__ and \
                 self.stream==other.stream and self.id==other.id)

    def __ne__(self, other):
        return not (self==other)

    def path(self):
        return '%s%s.html' % (self.stream.path(),
                              self.stream.itemIDField.convertToString(self.id))

    def initFieldFromCode(self, field_name, value):
        '''Initialize field from code'''
        field_type = self.stream.allStreamFields[field_name]
        value = field_type.convertFromCode(value, item=self)
        setattr(self, field_name, value)

    def initFieldsFromForm(self, form, names=None):
        '''Initialize item fields from data in form.  Return dictionary
        {field_name: error_message, ...} (empty if initialization is
        successful).'''
        errors = {}
        if names is None:
            names = self.stream.allItemFields.keys()
        for field_name in names:
            field_type = self.stream.allItemFields[field_name]
            if field_type.initFromForm:
                try:
                    value = field_type.convertFromForm(form, field_name, self)
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
        # XXX store external fields here?
        raise NotImplementedError()

    def touch(self):
        '''Touch the item (i.e. mark as its updated and need to be remaked)'''
        raise NotImplementedError()

    def delete(self):
        '''Delete item from DB'''
        self.stream.deleteItems([self.id])

    # --- External fields ---
    def retrieveExtFields(self):
        if not self._ext_fields_retrieved:
            for field_name, field_type in self.stream.itemExtFields.items():
                value = field_type.retrieve(item=self)
                setattr(self, field_name, value)
            self._ext_fields_retrieved = 1

    def storeExtField(self, field_name):
        field_type = self.stream.itemExtFields[field_name]
        field_type.store(getattr(self, field_name), item=self)

    def storeExtFields(self, names=None):
        '''For each external field store it, if its listed in names.  By
        default store all external fields.'''
        for field_name, field_type in self.stream.itemExtFields.items():
            if field_type.storeControl!='never' and \
                    (field_type.storeControl=='always' or \
                     names is None or field_name in names):
                self.storeExtField(field_name)

    def deleteExtFields(self):
        self.stream.deleteExtFields([self.id])


class Stream(Brick):
    '''Base class for streams'''

    type = 'stream'
    itemFieldsOrder = []
    itemFields = {}
    itemExtFields = {}
    class _ItemIDFieldFromSite(object):
        def __get__(self, inst, cls):
            if inst is None:
                return self
            return inst.site.defaultItemIDField
    itemIDField = _ItemIDFieldFromSite()

    def __init__(self, site, id, page=0, **kwargs):
        Brick.__init__(self, site, id)
        # updating stream parameters (first round)
        self.__dict__.update(kwargs)
        if self.tableName:
            self.itemFieldsOrder = site.itemFieldsOrder.get(
                self.tableName, self.itemFieldsOrder)
            self.itemFields = site.itemFields.get(
                self.tableName, self.itemFields)
            self.itemExtFields = site.itemExtFields.get(
                self.tableName, self.itemExtFields)
            self.itemIDField = site.itemIDFields.get(
                self.tableName, self.itemIDField)
        # XXX Implement joinFields as descriptor in SQLStream
        if hasattr(self, 'joinTable'):
            self.joinFields = site.itemFields.get(self.joinTable, {})
        # updating stream parameters (second round)
        self.__dict__.update(kwargs)
        if page<1:
            page = 1
        self.page = page
        # the list of items
        self.itemList = []
        # XXX Change to self.virtual.applyToStream(self)
        if hasattr(self, 'virtual'):
            self.addToCondition(self.virtual.condition(self))

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

    def allItemFields(self):
        '''Returns all bricks fields'''
        result = self.itemFields.copy()
        result.update(self.itemExtFields)
        return result
    allItemFields = qUtils.CachedAttribute(allItemFields)

    def allStreamFields(self):
        # XXX Override it in SQLStream to add joinFields support
        join_fields = getattr(self, 'joinFields', {})
        if join_fields:
            result = self.allItemFields.copy()
            result.update(join_fields)
            return result
        else:
            return self.allItemFields
    allStreamFields = qUtils.CachedAttribute(allStreamFields)

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
                itemDict[str(item.id)] = item
        return self.itemDict.get(str(item_id), None)

    def retrieveItem(self, item_id):
        item = self.getItem(item_id)
        if item is None:
            if not hasattr(self, 'retrieveItemCache'):
                self.retrieveItemCache = {}
            if not self.retrieveItemCache.has_key(str(item_id)):
                item = self.itemClass(self.site, self, item_id)
                if item.retrieve()!=1:
                    item = None
                self.retrieveItemCache[str(item_id)] = item
            return self.retrieveItemCache.get(str(item_id), None)
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

    def createNewItem(self, item_id=None):
        item = self.itemClass(self.site, self, item_id)
        defaults = self.brickDefaults
        if hasattr(self, 'virtual'):
            virtual_param_names = self.virtual.itemParamNames
        else:
            virtual_param_names = []
        for field_name, field_type in self.allItemFields.items():
            if field_name in virtual_param_names:
                value = getattr(self, field_name)
            elif defaults.has_key(field_name):
                value = field_type.convertFromCode(defaults[field_name], item)
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

    # --- External fields ---
    def deleteExtFields(self, item_ids):
        for field_name, field_type in self.itemExtFields.items():
            field_type.delete(item_ids, stream=self)


# vim: ts=8 sts=4 sw=4 ai et
