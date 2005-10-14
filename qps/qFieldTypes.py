# $Id: qFieldTypes.py,v 1.70 2005/09/04 21:24:42 corva Exp $

'''Classes for common field types'''

from __future__ import generators

import types, os, re, sys, weakref, logging
logger = logging.getLogger(__name__)

from mx import DateTime
import time

import qUtils


class _LayoutDict(dict):
    # This class is defined to keep compatimility with old field templates
    def __init__(self, *args, **kwargs):
        for d in args+(kwargs,):
            self.update(d)
    def __str__(self):
        return ' '.join(['%s="%s"' % t for t in self.items()])


class FieldType(object):
    '''Base class for all field types'''
    # storeControl:
    #   None        - store if user has sufficient priveleges
    #   'always'    - always store (useful for automatically updated fields)
    #   'never'     - never store (useful when another procedure to store data
    #                 is defined as it's done for multifield or for
    #                 automatically updated by DB trigers fields)
    storeControl = None
    # omitForNew    - if True omit value when new item is stored
    omitForNew = 0
    # Allow initialization of field from form (disallowed for multifield)
    initFromForm = 1
    # showField in binding view
    showInBinding    = 0
    linkThrough      = 1
    
    templateCat = None
    default     = ''                            # default value
    permissions = [('all', 'rw')] # permissions for item view
    # permissions for item create stage
    createPermissions  = qUtils.ReadAliasAttribute('permissions')
    indexPermissions = [] # permission for stream view
    layout      = _LayoutDict()                 # used in field template
    title       = '?'
    indexTitle  = qUtils.ReadAliasAttribute('title')
   
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        # quote class name to conform css rules
        className = self.__class__.__name__.replace('_', '')
        self.layout = _LayoutDict(self.layout, {'class': className})

    def __call__(self, **kwargs):
        # For compatibility: return a copy with some parameters changed.  Allow
        # us to use existing type as template.
        copy = self.__class__(**self.__dict__)
        copy.__dict__.update(kwargs)
        return copy

    def getDefault(self, item=None):
        return self.convertFromCode(self.default, item)
    
    def show(self, item, name, template_type, template_getter,
             global_namespace={}):
        '''Return HTML representation of field in editor interface
        item    - item object
        name    - field name
        user    - login of user, requested this operation'''
        value = getattr(item, name)
        if value is None:
            value = self.convertToForm(self.getDefault(item))
        else:
            value = self.convertToForm(value)
        namespace = global_namespace.copy()
        namespace.update({'title': name, 'value': value,
                          'item': item, 'brick': self})
        namespace.setdefault('name', name)
        template = self.getTemplate(template_type, template_getter)
        return template(namespace)

    def getTemplate(self, template_type, template_getter):
        if self.templateCat is not None:
            # Such templates MUST exist and MUST NOT be cached in class
            return template_getter('%s.%s' % (self.templateCat, template_type))
        from qWebUtils import TemplateNotFoundError
        for cls in self.__class__.__mro__:
            if not cls.__dict__.has_key('_templates'):
                cls._templates = {}
            if not cls._templates.has_key(template_type):
                try:
                    template = template_getter(
                                    '%s.%s' % (cls.__name__, template_type))
                except TemplateNotFoundError:
                    if cls is FieldType:
                        raise
                    else:
                        continue
                cls._templates[template_type] = template
            return cls._templates[template_type]

    def _identity(self, value, item=None): return value
    convertToDB = convertToForm = _identity
    def convertToString(self, value, item=None): return str(value)
    def convertFromCode(self, value, item=None): return value
    def convertFromDB(self, value, item=None): return value
    def convertFromString(self, value, item=None): return value
    def convertFromForm(self, form, name, item=None):
        return self.convertFromString(form.getfirst(name, ''), item)

    class InvalidFieldContent(Exception):
        '''Use this exception in convertFromForm method when value supplied by
        user is incorrect.  Pass error message as parameter.  For example:
               def convertFromForm(self, form, name, item=None):
                   try:
                       value = DateTime(value)
                   except:
                       raise InvalidFieldContent(
                           "Invalid date format or value")
        '''

        def __init__(self, message):
            self.message = message


class ExternalStoredField:
    "Interface for external stored fields"
    
    def retrieve(self, item):
        "Returns a field value from external storage"

    def store(self, value, item):
        "Stores a value in external storage"

    def delete(self, item_ids, stream):
        "Deletes values in external storage for item_ids"


class ExternalTableStoredField(ExternalStoredField):
    "Interface for fields stored in external tables"

    tableName = None       # Table name where values are stored.
    valueFieldName = None  # Name of table field where field value is stored.
    idFieldName = 'id'     # Name of table  where id of item is stored.

    def condition(self, item):
        from qDB.qSQL import Query, Param
        return Query('%s=' % self.idFieldName, Param(item.id))
    

class STRING(FieldType):
    minlength = 0
    maxlength = 255
    allowNull = False
    pattern = ''
    length_error_message = 'Text must consist of from %(brick.minlength)s ' \
                           'to %(brick.maxlength)s characters'
    not_match_error_message = 'String have to match pattern'
    stringCharset = 'utf-8' # charset used for converting unicode values to
                            # 8bit strings

    def __init__(self, **kwargs):
        FieldType.__init__(self, **kwargs)
        self.layout = _LayoutDict(self.layout, {'maxlength': self.maxlength})
        
    def convertFromForm(self, form, name, item=None):
        value = form.getString(name, '').strip()
        if self.allowNull and not value:
            return None
        if len(value) < self.minlength or len(value) > self.maxlength:
            message = qUtils.interpolateString(self.length_error_message,
                                               {'brick': self})
            raise self.InvalidFieldContent(message)
        if self.pattern and not re.match(self.pattern, value):
            raise self.InvalidFieldContent(self.not_match_error_message)
        return value

    def convertToString(self, value, item=None):
        if self.allowNull and not value:
            return ''
        if type(value) == unicode:
            return value.encode(self.stringCharset)
        else:
            return value

    def convertFromString(self, value, item=None):
        if self.allowNull and not value:
            return None
        # XXX dbCharset here is used as indicator of unicode mode 
        if item.site.dbCharset:
            return value.decode(self.stringCharset)
        else:
            return value

    def convertFromDB(self, value, item):
        if value is None:
            return value
        if item.dbConn.charset:
            value = value.decode(item.dbConn.charset)
        return value

    def convertToDB(self, value, item):
        if item.dbConn.charset:
            value = value.encode(item.dbConn.charset)
        return value


class STRING_ID(STRING):
    title = 'ID'
    minlength = 1
    maxlength = 32
    pattern = '^[0-9a-zA-Z_-]+$'
    not_match_error_message = 'ID can contain latin alfanumeric characters, '\
                              'underscores and dashes only'
    permissions = [('all', 'r')]
    createPermissions = [('all', 'rw')]
    indexPermissions = [('all', 'r')]
    showInBinding = 1


class UNIQUE_STRING(STRING):
    """Unique string value for a table's column. Useful for database column
    described as UNIQUE INDEX"""

    unique_error = "%(brick.title)s is already used, try a different one."
    
    def convertFromForm(self, form, name, item=None):
        value = STRING.convertFromForm(self, form, name, item)
        if value is None:
            return value  # NULL (if allowed) is not required to be unique
        from qps.qDB.qSQL import Query, Param
        conn = item.dbConn
        query = Query("%s=" % name, Param(self.convertToDB(value, item)))
        if item.exists():
            query = conn.join([query, Query("%s !=" % item.fields.idFieldName,
                                            Param(item.id))])
        row = conn.selectRow(item.stream.tableName, [name], query)
        if row:
            message = qUtils.interpolateString(self.unique_error,
                                               {'brick': self})
            raise self.InvalidFieldContent(message)
        return value

    
class NUMBER(FieldType):

    type = None
    type_name = "Number"
    default = 0
    min_value = 0
    max_value = sys.maxint
    error_message = '%(brick.type_name)s from %(brick.min_value)s to '\
                    '%(brick.max_value)s required'

    def __init__(self, **kwargs):
        FieldType.__init__(self, **kwargs)
        self.maxlength = max(len(str(self.max_value)),
                             len(str(self.min_value))) + 1
        self.layout = _LayoutDict(self.layout, {'maxlength': self.maxlength})

    def convertFromString(self, value, item=None):
        return self.type(value)

    def convertFromForm(self, form, name, item=None):
        value = form.getfirst(name, '').strip()
        if not value:
            value = self.getDefault(item)
        message = qUtils.interpolateString(self.error_message, {'brick': self})
        try:
            value = self.type(value)
        except ValueError:
            raise self.InvalidFieldContent(message)
        if self.min_value<=value<=self.max_value:
            return value
        else:
            raise self.InvalidFieldContent(message)

    def convertFromDB(self, value, item=None):
        return self.type(value)
    

class INTEGER(NUMBER):
    type = int
    type_name = "Integer"


class INTEGER_AUTO_ID(INTEGER):
    title = 'ID'
    omitForNew = 1
    permissions = [('all', '')]
    indexPermissions = [('all', 'r')]
    showInBinding = 1


class PASSWORD(FieldType):

    minlength = 5
    too_short_message = 'Password must be at least %(brick.minlength)s ' \
                        'characters long'
    confirmation_failed_message = 'Passwords donot match'
    encoding_failed_message = 'Password must consist only from latin ' \
                              'characters, spaces, underscores and digits'

    def crypt(self, value):
        # Don't encrypt by default
        return value

    def convertFromForm(self, form, name, item):
        value = form.getfirst(name, '').strip()
        old_value = getattr(item, name)
        if value or not old_value:
            if len(value)<self.minlength:
                message = qUtils.interpolateString(self.too_short_message,
                                                   {'brick': self})
                raise self.InvalidFieldContent(message)
            confirm = form.getfirst(name+'-confirm', '').strip()
            if value!=confirm:
                message = qUtils.interpolateString(
                            self.confirmation_failed_message, {'brick': self})
                raise self.InvalidFieldContent(message)
            try:
                value = str(value)
            except UnicodeEncodeError:
                raise self.InvalidFieldContent(self.encoding_failed_message)
            return self.crypt(value)
        else:
            # leave unchanged
            return old_value


class DIGESTPASSWORD(PASSWORD):

    from md5 import new as digest

    def crypt(self, value):
        return self.digest(value).hexdigest()


class DATETIME(FieldType):
    format = '%d.%m.%Y %H:%M'
    error_message = 'Invalid date format'
    default = 'now'
    allowNull = False
    def convertFromCode(self, value, item=None):
        if value=='now':
            return DateTime.now()
        elif not value:
            return
        else:
            # DateTime.strptime is not available on Windows
            return DateTime.DateTime(*time.strptime(value, self.format)[:6])
    convertFromString = convertFromCode
    def convertToString(self, value, item=None):
        if value is None:
            return ''
        else:
            return value.strftime(self.format)
    def convertToForm(self, value):
        if value is None:
            return ''
        else:
            return value.strftime(self.format)
    def convertFromForm(self, form, name, item=None):
        value = form.getfirst(name, '').strip()
        if not value and self.allowNull:
            return
        try:
            # DateTime.strptime is not available on Windows
            return DateTime.DateTime(*time.strptime(value, self.format)[:6])
        except:
            message = qUtils.interpolateString(self.error_message,
                                               {'brick': self})
            raise self.InvalidFieldContent(message)


class AUTO_TS(DATETIME):
    permissions = []
    storeControl = "always"
    allowNull = True
    default = None

    def convertToDB(self, value, item):
        from qDB.qSQL import Raw
        return Raw("NOW()")
        

class TEXT(STRING):
    layout = _LayoutDict({'cols': 60, 'rows': 10, 'wrap': 'virtual',
                          'style': 'width: 100%'})
    maxlength = 65535
    lengthInIndex = 250


class DROP(FieldType):
    extraOption = None
    labelTemplate = '%(quoteHTML(getattr(brick, "title", str(brick.id))))s'

    def _retrieve_stream(self, item):
        stream, tag = self._stream_params(item)
        return item.site.retrieveStream(stream, tag=item.site.transmitTag(tag))

    def _stream_params(self, item):
        return (self.stream, item.stream.tag)

    def show(self, item, name, template_type, template_getter,
             global_namespace={}):
        namespace = global_namespace.copy()
        namespace.update({'stream': self._retrieve_stream(item)})
        return FieldType.show(self, item, name, template_type, template_getter,
                              namespace)

    def getLabel(self, item):
        '''Return label for option defined by item'''
        namespace = item.site.globalNamespace.copy()
        namespace.update({'brick': item})
        return qUtils.interpolateString(self.labelTemplate, namespace)


class SELECT(DROP):
    layout = _LayoutDict({'size': 5, 'multiple': 'multiple'})
    default = []
    fieldSeparator = ','
    def convertToDB(self, value, item=None):
        stream = item.site.retrieveStream(self.stream,
                                tag=item.site.transmitTag(item.stream.tag))
        return self.fieldSeparator.join(
                        map(stream.fields.id.convertToString, value)+[''])
    def convertFromDB(self, value, item=None):
        stream = item.site.retrieveStream(self.stream,
                                tag=item.site.transmitTag(item.stream.tag))
        return map(stream.fields.id.convertFromString,
                   value.split(self.fieldSeparator)[:-1])
    def convertFromForm(self, form, name, item=None): 
        return form.getlist(name)
        

class LazyItem:
    """Base class for other Lazy Classes, it is supposed to be stored into
    field of item as a references to other item without retrieving it untill
    it is really neccessary"""
    
    def __init__(self, site, stream_params, item_id):
        self._site = site # it's already a weakref
        self._stream_id, self._stream_tag = stream_params
        self._item_id = item_id

    def _stream(self):
        return self._site.retrieveStream(
            self._stream_id,
            tag=self._site.transmitTag(self._stream_tag))

    def _item(self):
        "Returns item, should be redefined in childs"
        pass

    def __nonzero__(self):
        return self._item is not None

    def __getattr__(self, name):
        if name in ('_item', '__del__'):
            # XXX Avoid unlimited recursion due
            # to bug in descriptors
            # implementation in 2.2
            raise AttributeError(name)
        return getattr(self._item, name)

    def __setattr__(self, name, value):
        if name in ('_site', '_stream_id', '_stream_tag', '_item_id', '_item'):
            self.__dict__[name] = value
        else:
            setattr(self._item, name, value)

    def __repr__(self):
        return '<LazyItem for stream_id=%r id=%r>' % (self._stream_id,
                                                      self._item_id)

class RetrievedLazyItem(LazyItem):
    """This class retrieves item from db w/o retrieving whole stream"""
    
    def _item(self):
        return self._stream().retrieveItem(self._item_id)
    _item = qUtils.CachedAttribute(_item)


class GettedLazyItem(LazyItem):
    """This class retrieves item retrieves stream and get item with getItem"""
    
    def _item(self):
        return self._stream().getItem(self._item_id)
    _item = qUtils.CachedAttribute(_item)


class FOREIGN_DROP(FieldType):
    proxyClass = RetrievedLazyItem
    extraOption = None
    missingID = None # representation of missing value in DB (default is NULL)
    allowNull = True # allow null values from form
    default = None
    labelTemplate = '%(quoteHTML(getattr(brick, "title", str(brick.id))))s'
    null_not_allowed_error = "Your have to select something"

    def _retrieve_stream(self, item):
        stream, tag = self._stream_params(item)
        return item.site.retrieveStream(stream, tag=item.site.transmitTag(tag))

    def _stream_params(self, item):
        return (self.stream, item.stream.tag)

    def convertFromCode(self, value, item):
        if value is not None:
            return self.proxyClass(item.site, self._stream_params(item),
                                   value)

    def convertFromDB(self, value, item):
        if value!=self.missingID:
            return self.proxyClass(item.site, self._stream_params(item),
                                   value)
    
    def convertToDB(self, value, item=None):
        if value: # calls LazyItem.__nonzero__ that checks for None
            return value.stream.fields.id.convertToDB(value.id, item)
        else:
            return self.missingID

    def convertToString(self, value, item=None):
        if value:
            return value.stream.fields.id.convertToString(value.id, item)
        else:
            return ''

    def convertFromString(self, value, item=None):
        if value:
            stream = self._retrieve_stream(item)
            id = stream.fields.id.convertFromString(value, item)
            return self.proxyClass(item.site, self._stream_params(item), id)
        else:
            return None

    def convertFromForm(self, form, name, item):
        value = form.getfirst(name, '')
        if value:
            stream = self._retrieve_stream(item)
            value = self.proxyClass(item.site,
                                    self._stream_params(item),
                                    stream.fields.id.convertFromString(value,
                                                                       item))
            if not (self.allowNull or value):
                raise self.InvalidFieldContent(self.null_not_allowed_error)
            else:
                return value

    def getLabel(self, item):
        namespace = item.site.globalNamespace.copy()
        namespace.update({'brick': item})
        return qUtils.interpolateString(self.labelTemplate, namespace)

    def show(self, item, name, template_type, template_getter,
             global_namespace={}):
        namespace = global_namespace.copy()
        namespace.update({'stream': self._retrieve_stream(item)})
        return FieldType.show(self, item, name, template_type, template_getter,
                              namespace)


class FOREIGN_MULTISELECT(FOREIGN_DROP):
    fieldSeparator = ','
    default = []
    columns = 3 # number of columns to display in field template
    
    def inList(self, id, items):
        return id in [item.id for item in items]

    def convertFromCode(self, values, item):
        # XXX Bug here! Missing (or just unpublished) items are not filtered
        # out! We must use somethong like LazyItemList to keep laziness.
        return [FOREIGN_DROP.convertFromCode(self, value, item)
                for value in values]

    def convertFromString(self, value, item):
        if value:
            item_ids = value.split(self.fieldSeparator)
            stream = self._retrieve_stream(item)
            return self.convertFromCode(
                [stream.fields.id.convertFromString(id, item) \
                 for id in item_ids], item)
        else:
            return []
    convertFromDB = convertFromString

    def convertFromForm(self, form, name, item):
        value = form.getlist(name)
        stream = self._retrieve_stream(item)
        return self.convertFromCode(
                    [stream.fields.id.convertFromString(id, item) \
                     for id in  value], item)

    def convertToString(self, value, item=None):
        item_ids = [FOREIGN_DROP.convertToString(self, item, item)
                    for item in value]
        return self.fieldSeparator.join(item_ids)
    convertToDB = convertToString

    def getIndexLabel(self, value):
        views = [FOREIGN_DROP.getLabel(self, i)
                 for i in value]
        return ', '.join(views)

    def setValue(self, item, name, value):
        setattr(item, name, getattr(item, name)+ [value])

        
class BOOLEAN(FieldType):
    """Bool field type, handles True/False values.

    Attributes:
    
    dbTrue - database value of True (default 1)
    dbFalse - database value of False (default 0)

    bool(dbTrue) must be True and bool(dbFalse) must be False"""
    
    dbTrue = 1
    dbFalse = 0
    
    def convertFromDB(self, value, item):
        return bool(value)

    def convertFromForm(self, form, name, item):
        value = form.getfirst(name, '')
        return bool(value)

    def convertToDB(self, value, item):
        return value and self.dbTrue or self.dbFalse
    

class CB_YN(BOOLEAN):
    """Obsolete fieldtype, it was represented in database as enum('y', ''),
    use BOOLEAN instead."""
    
    dbTrue = 'y'
    dbFalse = ''


class EXT_FOREIGN_MULTISELECT(FOREIGN_MULTISELECT, ExternalTableStoredField):
    linkThrough = 0
    countTemplate = '%(count or "no")s item(s)'
    itemField = STRING() # field type of values
    
    class LazyItemList:
        def __init__(self, field_type, item):
            self.field_type = field_type
            self.item = weakref.proxy(item)

        def _items(self):
            conn = self.item.dbConn
            field_type = self.field_type
            db_values = conn.selectFieldAsList(
                    field_type.tableName, field_type.valueFieldName,
                    field_type.condition(self.item))
            items = []
            for db_value in db_values:
                items.append(
                    field_type.itemField.convertFromDB(db_value,
                                                       item=self.item))
            return filter(None, items)
        _items = qUtils.CachedAttribute(_items)

        def __getitem__(self, index):
            return self._items[index]

        def __setitem__(self, index, value):
            self._items[index] = value

        def __len__(self):
            return len(self._items)

        def __iter__(self):
            return iter(self._items)

        def append(self, obj):
            self._items.append(obj)

        def index(self, obj):
            return self._items.index(obj)

        def __contains__(self, obj):
            return obj in self._items

        def __delitem__(self, index):
            del self._items[index]

        def __eq__(self, other):
            return self._items==other

        def __ne__(self, other):
            return not (self==other)

        def remove(self, value):
            return self._items.remove(value)


    def __init__(self, **kwargs):
        FOREIGN_MULTISELECT.__init__(self, **kwargs)
        self.itemField = FOREIGN_DROP(stream=kwargs['stream'])

    def retrieve(self, item):
        return self.LazyItemList(self, item)

    def store(self, values, item):
        db_values = []
        for value in values:
            db_values.append(self.itemField.convertToDB(value, item))
        conn = item.dbConn
        all_cond = delete_cond = self.condition(item)
        if db_values:
            delete_cond = conn.join(
                    [delete_cond, conn.NOT_IN(self.valueFieldName, db_values)])
        tnx = conn.getTransaction()
        old_db_values = conn.selectFieldAsList(self.tableName,
                                               self.valueFieldName, all_cond)
        conn.delete(self.tableName, delete_cond)
        for db_value in db_values:
            if db_value not in old_db_values:
                item.dbConn.insert(self.tableName, {self.idFieldName: item.id,
                                            self.valueFieldName: db_value})
        tnx.close()

    def delete(self, item_ids, stream):
        if item_ids:
            tnx = stream.dbConn.getTransaction()
            stream.dbConn.delete(self.tableName,
                                 stream.dbConn.IN(self.idFieldName, item_ids))
            tnx.close()

    def getIndexLabel(self, value):
        count = len(value)
        return qUtils.interpolateString(self.countTemplate, {'count': count})


class EXT_VIRTUAL_REFERENCE(FieldType, ExternalStoredField):

    default = None
    paramName = None       # optional
    permissions = [('all', 'r')]
    linkThrough = 0
    templateStream = None  # must be set
    rule = None
    omitForNew = 1
    storeControl = 'never'
    rewriteToStream = None

    class LazyVirtual:
        def __init__(self, item, template_stream, param_name=None,
                     rule_id=None, rewrite_to_stream=None):
            self._item = weakref.proxy(item)
            self._template_stream = template_stream
            self._param_name = param_name
            self._rewrite_to_stream = rewrite_to_stream
            self._rule_id = rule_id
        def _stream(self):
            item = self._item
            if self._rewrite_to_stream is not None and \
                   item.stream.id!=self._rewrite_to_stream:
                new_stream = item.site.retrieveStream(self._rewrite_to_stream,
                                                      # NB: no transmission
                                                      # here!
                                                      tag=item.stream.tag)
                item = new_stream.retrieveItem(item.id)
                if item is None:
                    return
            
            for stream in item.virtualStreams:
                template_stream = getattr(stream.virtual, 'templateStream',
                                          None)
                if self._rule_id and stream.virtual.id == self._rule_id:
                    return stream
                if template_stream is not None and \
                        template_stream==self._template_stream and \
                        (self._param_name is None or \
                         self._param_name==getattr(stream.virtual,
                                                   'paramName', None)):
                    return stream
        _stream = qUtils.CachedAttribute(_stream)
        def __nonzero__(self):
            return self._stream is not None
        def __getattr__(self, name):
            if name in ('_stream', '__del__'): # XXX Avoid unlimited
                                               # recursion due to bug in 
                                               # decriptiors implementation
                                               # in 2.2
                raise AttributeError(name)
            return getattr(self._stream, name)

    def retrieve(self, item):
        return self.LazyVirtual(item, self.templateStream,
                                param_name=self.paramName,
                                rewrite_to_stream=self.rewriteToStream,
                                rule_id=self.rule)

    def store(self, value, item):
        pass

    def delete(self, item_ids, stream):
        pass

    def getDefault(self, item=None):
        return self.retrieve(item)


class IMAGE(FieldType, ExternalStoredField):

    editRoot = None
    pathTemplate = '/images/%(brick.id)s'
    bad_image_message = 'Unknown format or broken image'
    format_not_allowed_message = 'Format %(image.format_description)s '\
                                 'is not allowed'
    allowed_formats = ('GIF', 'PNG', 'JPEG')
    linkThrough = 0
    allowUrl = False
    allowFile = True
    
    class _Image:
        def __init__(self, field_type, item, body=None, old_path=None):
            self.item = weakref.proxy(item)
            self.field_type = field_type
            self.body = body
            self.old_path = old_path
        def pattern(self):
            namespace = self.item.site.globalNamespace.copy()
            namespace.update({'brick': self.item})
            return qUtils.interpolateString(self.field_type.pathTemplate,
                                            namespace)
        pattern = qUtils.CachedAttribute(pattern)
        def path(self):
            if self.body:
                return self.pattern+'.'+self._image.format.lower()
            else:
                from glob import glob
                file_list = glob(self.field_type.editRoot+self.pattern+'.*')
                if file_list:
                    # Fix slashes to work on non-POSIX platforms
                    file_name = '/'.join(os.path.split(file_list[0]))
                    return file_name[len(self.field_type.editRoot):]
        path = qUtils.CachedAttribute(path)
        def __str__(self):
            return self.path
        def __nonzero__(self):
            return self.path is not None
        def _image(self):
            if self.body is None:
                if self.path is None:
                    return
                fp = open(self.field_type.editRoot+self.path)
            elif not self.body:
                return
            else:
                from cStringIO import StringIO
                fp = StringIO(self.body)
            import PIL.Image
            try:
                return PIL.Image.open(fp)
            except IOError:
                logger.warn('Broken image in %s', getattr(fp, 'name', '?'))
                return
        _image = qUtils.CachedAttribute(_image)

    def convertFromForm(self, form, name, item):
        old_path =  getattr(getattr(item, name), 'path', None)
        if form.has_key(name+'-delete'):
            return self._Image(self, item, '', old_path)

        sources = []
        if self.allowFile:
            try:
                sources.append(form[name+'-body'].file)
            except (KeyError, AttributeError):
                pass
        if self.allowUrl:
            try:
                url = form.getfirst(name+'-url')
                if url:
                    referer = '/'.join(url.split('/')[:-1])+'/'
                    import urllib2
                    req = urllib2.Request(url=url)
                    req.add_header('Referer', referer)
                    sources.append(urllib2.urlopen(req))
            except ValueError:
                pass
            except IOError, why:
                raise self.InvalidFieldContent(why)

        image = self._Image(self, item)
        for source in sources:
            if source is None:
                continue
            image_body = source.read()
            if not image_body:
                continue
            image = self._Image(self, item, image_body, old_path)
            break
        else:
            return image

        if image._image is None:
            message = qUtils.interpolateString(self.bad_image_message,
                                               {'brick': self})
            raise self.InvalidFieldContent(message)
        if image._image.format not in self.allowed_formats:
            message = qUtils.interpolateString(self.format_not_allowed_message,
                                       {'brick': self, 'image': image._image})
            raise self.InvalidFieldContent(message)
        return image

    def retrieve(self, item):
        return self._Image(self, item)

    def convertFromCode(self, value, item):
        return self.retrieve(item)

    def store(self, value, item):
        if value.body:
            if value.old_path is not None:
                 os.remove(self.editRoot+value.old_path)
            # hack to reset chached value for new item
            try:
                del value.pattern
            except AttributeError:
                pass
            try:
                del value.path
            except AttributeError:
                pass
            qUtils.writeFile(self.editRoot+value.path, value.body)
        elif value.body is not None:
            os.remove(self.editRoot+value.path)

    def delete(self, item_ids, stream):
        for item_id in item_ids:
            item = stream.retrieveItem(item_id)
            image = self._Image(self, item)
            if image:
                os.remove(self.editRoot+image.path)


class RESTRICTED_IMAGE(IMAGE):
    # maxWidth and maxHeight are obsoleted, use width and height
    maxWidth = None
    maxHeight = None
    width  = qUtils.ReadAliasAttribute('maxWidth')
    height = qUtils.ReadAliasAttribute('maxHeight')

    def resizeFilter(self):
        import PIL.Image
        return PIL.Image.ANTIALIAS
    resizeFilter = property(resizeFilter)

    def convertFromForm(self, form, name, item):
        value = IMAGE.convertFromForm(self, form, name, item)
        image = image_orig = value._image

        if value.body and image:
            w,h = image.size
            maxw, maxh = self.width, self.height

            if maxw and w > maxw:
                image = image.resize((maxw, maxw*h/w), self.resizeFilter)
                w,h = image.size
            if maxh and h > maxh:
                image = image.resize((w*maxh/h, maxh), self.resizeFilter)

            if image != image_orig:
                from cStringIO import StringIO
                fp = StringIO()
                image.save(fp, image_orig.format)
                fp.seek(0)
                value = self._Image(self, item, fp.read(),
                                    getattr(getattr(item, name), 'path', None))

        return value


class THUMBNAIL(IMAGE):
    
    fieldToThumb = None
    width = 0  # define correct sizes of thumbnail
    height = 0

    def resizeFilter(self):
        import PIL.Image
        return PIL.Image.ANTIALIAS
    resizeFilter = property(resizeFilter)
    
    def convertFromForm(self, form, name, item):
        if self.fieldToThumb:
            # we have field to thumbnail
            _image = getattr(item, self.fieldToThumb, None)
            image = image_orig = getattr(_image, '_image', None)
        else:
            # field thumbnails itself
            if form.has_key(name+'-delete'):
                old_path =  getattr(getattr(item, name), 'path', None)
                return self._Image(self, item, '', old_path)

            _image = IMAGE.convertFromForm(self, form, name, item)
            image = image_orig = getattr(_image, '_image', None)

        if not _image.body:
            # image was not updated
            return _image

        if image and self.width and self.height:
            image = self.thumbnail(image)
            from cStringIO import StringIO
            fp = StringIO()
            image.save(fp, image_orig.format)
            fp.seek(0)
            return self._Image(self, item, fp.read(),
                               getattr(getattr(item, name), 'path', None))
        else:
            return self._Image(self, item)

    def thumbnail(self, image):
        w,h = image.size
        logger.debug('orig image: %sx%s', w, h)

        if float(h)/w > float(self.height)/self.width:
            size = (self.width, self.width*h/w)
            image = image.resize(size, self.resizeFilter)
            w,h = image.size
            logger.debug('resized image: %sx%s', w, h)
            rect = (0,
                    (h-self.height)/2,
                    self.width,
                    (h-self.height)/2+self.height
                    )
            logger.debug('crop frame: %s', str(rect))
            image = image.crop(rect)
        else:
            size = (self.height*w/h, self.height)
            image = image.resize(size, self.resizeFilter)
            w,h = image.size
            logger.debug('resized image: %sx%s', w, h)
            rect = ((w-self.width)/2,
                    0,
                    (w-self.width)/2+self.width,
                    self.height
                    )
            logger.debug('crop frame: %s', str(rect))
            image = image.crop(rect)
        return image

    
class AgregateFieldType(FieldType):

    def _unescape(self, string):
        return re.sub(r'\\(.)', r'\1', string)

    def convertFromDB(self, value, item=None):
        return self.convertFromString(value, item)

    def convertToDB(self, value, item):
        return self.convertToString(value, item)

    class _Proxy:
        def __init__(self, item, ext_fields):
            self.__item = item
            self.__dict__.update(ext_fields)
        def __getattr__(self, name):
            return getattr(self.__item, name)

    def getDefault(self, item=None):
        return self.convertFromString('', item)


class CONTAINER(AgregateFieldType):

    fields = [] # FieldDescriptions instance needed
    dictClass = qUtils.DictRecord

    def _split(self, string):
        return [(self._unescape(key), self._unescape(field))
                for key, field in 
                    re.findall(r'(?:^|,)((?:[^\\:]|\\.)*):((?:[^\\,]|\\.)*)',
                               string)]

    def _join(self, seq):
        return ','.join([':'.join([self._escape(key), self._escape(field)])
                         for key, field in seq])

    def _escape(self, string):
        return re.sub(r'([,:\\])', r'\\\1', string)

    def _child_name(self, name, subname):
        return '.'.join([name, subname])

    def convertFromCode(self, value, item=None):
        # XXX Looks like broken. Need to test it
        result = self.dictClass()
        for key, field_type in self.fields:
            result[key] = field_type.convertFromCode(value[key], item)
        return result
    
    def convertFromString(self, string, item=None):
        result = self.dictClass()
        key_field_map = dict(self._split(string))
        for key, field_type in self.fields:
            try:
                field = key_field_map[key]
            except KeyError:
                result[key] = field_type.getDefault(item)
            else:
                result[key] = field_type.convertFromString(field, item)
        return result

    def convertToString(self, value, item=None):
        seq = []
        for key, field in value.items():
            field_type = self.fields[key]
            seq.append((key, field_type.convertToString(field, item)))
        return self._join(seq)

    def convertFromForm(self, form, name, item=None):
        result = self.dictClass()
        for subname, field_type in self.fields:
            result[subname] = field_type.convertFromForm(form,
                                    self._child_name(name, subname), item)
        return result

    def show(self, item, name, template_type, template_getter,
             global_namespace={}):
        value = getattr(item, name)
        subfields = []
        formname = global_namespace.pop('name', name)
        for subname, field_type in self.fields:
            full_name = self._child_name(formname, subname)
            proxied_item = self._Proxy(item, {full_name: value[subname]})
            subfields.append(field_type.show(proxied_item, full_name,
                                             template_type, template_getter,
                                             global_namespace))
        namespace = global_namespace.copy()
        namespace['subfields'] = subfields
        return FieldType.show(self, item, name, template_type, template_getter,
                              namespace)


class ARRAY(AgregateFieldType):

    length = 3
    itemField = STRING()

    def _split(self, string):
        return [self._unescape(field)
                for field in re.findall(r'((?:[^\\;]|\\.)*);', string)]

    def _join(self, seq):
        return ';'.join([self._escape(field) for field in seq])+';'

    def _escape(self, string):
        return re.sub(r'([;\\])', r'\\\1', string)

    def _child_name(self, name, index):
        return '%s-%s' % (name, index)

    def _fix_length(self, value, item):
        while len(value)<self.length:
            value.append(self.itemField.getDefault(item))
        return value[:self.length]
    
    def hideItem(self, value, tag=None):
        return value is None

    def _filter(self, values, item):
        tag = item.site.transmitTag(item.stream.tag)
        return [value for value in values if not self.hideItem(value, tag)]
    
    def convertFromCode(self, values, item=None):
        return self._filter([self.itemField.convertFromCode(value, item)
                             for value in values], item)
    
    def convertFromString(self, string, item=None):
        return self._filter([self.itemField.convertFromString(field, item)
                             for field in self._split(string)], item)

    def convertToString(self, value, item=None):
        return self._join([self.itemField.convertToString(field, item)
                           for field in value])

    def convertFromForm(self, form, name, item=None):
        return self._filter([self.itemField.convertFromForm(form,
                                    self._child_name(name, index), item)
                             for index in range(self.length)], item)

    def show(self, item, name, template_type, template_getter,
             global_namespace={}):
        value = self._fix_length(getattr(item, name), item)
        subfields = []
        for index in range(self.length):
            full_name = self._child_name(name, index)
            proxied_item = self._Proxy(item, {full_name: value[index]})
            subfields.append(self.itemField(title=str(index+1)).show(
                                    proxied_item, full_name, template_type,
                                    template_getter, global_namespace))
        namespace = global_namespace.copy()
        namespace['subfields'] = subfields
        return FieldType.show(self, item, name, template_type, template_getter,
                              namespace)


class FieldDescriptions(qUtils.Descriptions):
    """Storage for fields config.
    
    Usage:

        fields = FieldDescriptions([field1_name, field1_type_class(...),
                                    field2_name, field2_type_class(...),
                                    ...])

        id = fields.id
        for field_name, field_type in fields:
            pass
        for field_name, field_type in fields.iteritems():
            pass
        for field_name in fields.iterkeys():
            pass

        Class also defines attributes:

        external    - FieldDescriptions object for external fields (storable)
        main        - the same for main fields
        idFieldName - name of id field"""

    idFieldName = "id"
        
    def __init__(self, config, **kwargs):
        self._config = config
        self.__dict__.update(kwargs)

    def external(self):
        return self.__class__(
            [(fn, ft) for fn, ft in self._config if hasattr(ft, 'store')])
    external = qUtils.CachedAttribute(external)

    def main(self):
        return self.__class__(
            [(fn, ft) for fn, ft in self._config if not hasattr(ft, 'store')])
    main = qUtils.CachedAttribute(main)

    def id(self):
        return self[self.idFieldName]
    id = qUtils.CachedAttribute(id)

    
class FieldDescriptionsRepository:
    '''Wraps config (dictionary) values with FieldDescriptions class.
    
    Usage:
        fieldDescriptions = FieldDescriptionsRepository({
            'table1': [
                ('field1_name', field1_type_class(...),
                ...
            ],
            ...
        })
    '''

    def __init__(self, config):
        self._config = config
        self._cache = {}

    def __getitem__(self, table):
        if not self._cache.has_key(table):
            self._cache[table] = FieldDescriptions(self._config[table])
        return self._cache[table]

    def get(self, table, default=None):
        try:
            return self[table]
        except KeyError:
            return default


# vim: ts=8 sts=4 sw=4 ai et
