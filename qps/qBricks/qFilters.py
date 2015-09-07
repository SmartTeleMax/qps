"""Support for filtering QPS streams.

This module defines two types of classes:

StreamFilter - defines how stream is filtered. SQL stream filtering differs
               from XMLStream and Static strea,
FilterFieldsType - defines how fields are filtered. String fields can be
                   filtered with different methods - LIKE, EQUALS etc.

Configuration example.

1. Apply a filter object to streamDecsription:
DictRecord(title='Some stream', filter=SQLStreamFilter())

2. Apply filter fields classes to fieldDescriptions:
('title', FT.STRING(title='Document title',
                    filter=SQL_LIKE_STRING()))
"""

#
# Filter classes
#

class StreamFilter(object):
    """Filter object knows filter fields names for stream and can create
    new instance of stream with applied filter params"""

    def __nonzero__(self):
        """Returns True if filter changes the stream or False if it doesn't"""
        return False

    def fields(self, stream):
        """Returns a list of field names used in filter"""
        return [name for name, type in stream.fields.iteritems() if \
                getattr(type, 'filter', False)]

    def createField(self, field):
        "Returns FilterFieldType for field object"
        return field.filter.create(field)

    def createState(self, stream):
        """Returns a state item for filter"""
        state = stream.createNewItem()
        for name in self.fields(stream):
            setattr(state, name,
                    self.createField(stream.fields[name]).getDefault())
        return state

    def applyToStream(self, stream):
        """Applies parameters to stream instance"""


class SQLStreamFilter(StreamFilter):
    """Filter for SQL streams, operates with conditions and joinTemplates"""

    def __init__(self):
        self.conditions = []
        self.joinTemplates = []

    def __nonzero__(self):
        return bool(self.conditions or self.joinTemplates)

    def applyToStream(self, stream, cond_method="AND"):
        joinTemplate = getattr(stream, "joinTemplate", "%(brick.tableName)s")
        stream.joinTemplate = ' '.join([joinTemplate]+self.joinTemplates)
        stream.addToCondition(stream.dbConn.join(self.conditions, cond_method))
        return stream


#
# Filter field types classes
#

import qps.qFieldTypes as FT

class FilterFieldType:
    def create(self, field):
        """Returns a new instance of filter field initialized with required
        params from field"""
        return self(title=field.title)

    def applyToFilter(self, filter, item, name, value):
        """Changes filter state"""


#
# Conditions
#

from qps.qDB.qSQL import Query, Param

class SQLEquals:
    "Generates equal conditions on value"

    def applyToFilter(self, filter, item, name, value):
        filter.conditions.append(
            Query("%s.%s=" % (item.stream.tableName, name),
                  Param(self.convertToDB(value, item)))
            )


class SQLLikes:
    "Generates LIKE conditions on value"

    def applyToFilter(self, filter, item, name, value):
        filter.conditions.append(
            Query("%s.%s LIKE " % (item.stream.tableName, name),
                  Param('%'+self.convertToDB(value, item)+'%'))
            )


class SQL_EQUAL_STRING(SQLEquals, FilterFieldType, FT.STRING):
    pass


class SQL_LIKE_STRING(SQLLikes, FilterFieldType, FT.STRING):
    pass


class SQL_EQUAL_INTEGER(SQLEquals, FilterFieldType, FT.INTEGER):
    pass


class SQL_FOREIGN_DROP(SQLEquals, FilterFieldType, FT.FOREIGN_DROP):
    extraOption = " "

    def create(self, field):
        return self(title=field.title,
                    stream=self.stream or field.stream)


class SQL_EXT_FOREIGN_MULTISELECT(FilterFieldType, FT.FOREIGN_DROP):
    extraOption = " "

    def create(self, field):
        return self(title=field.title, stream=field.stream, orig=field)

    def applyToFilter(self, filter, item, name, value):
        filter.conditions.append(
            Query("%s.%s=" % (self.orig.tableName,
                              self.orig.valueFieldName),
                  Param(self.convertToDB(value, item)))
            )
        filter.joinTemplates.append(
            "JOIN " + self.orig.tableName + \
            " ON %(brick.tableName)s.%(brick.fields.idFieldName)s = " + \
            "%s.%s" % (self.orig.tableName, self.orig.idFieldName)
            )


class SQL_FOREIGN_CONTAINER(FilterFieldType, FT.CONTAINER):
    """Filters on fields of foreign item. To be used with FOREIGN_DROP fields.

    FOREIGN_DROP(stream='streamid',
                 filter=SQL_FOREIGN_CONTAINER(fields=FieldDescriptions())
                )

    fields param is supposed to be a FieldDescription of filter field objects,
    named with foreign item field names.

    fields = FieldDescriptions([
        ('firstname', SQL_EQUAL_STRING(title='First name')),
        ('address', SQL_LIKE_STRING(title='Part of address'))
        ])

    In example above firstname and address are names of fields in streamid.
    """

    def create(self, field):
        """Returns a new instance of filter field initialized with
        field.title, field.stream an field.filterFields"""
        return self(title=field.title, stream=field.stream)

    def applyToFilter(self, filter, item, name, value):
        # value is a dict
        foreignStream = item.site.createStream(self.stream)
        foreignItem = foreignStream.createNewItem()

        applied = False
        for n, v in [(n, v) for n, v in value.items() if v]:
            applied = True
            field = self.fields[n]
            field.applyToFilter(filter, foreignItem, n, v)

        if applied: # only add join template if subfields applied to filter
            filter.joinTemplates.append(
                "JOIN " + foreignStream.tableName + \
                " ON %(brick.tableName)s." + "%s = " % name + \
                "%s.%s" % (foreignStream.tableName,
                           foreignStream.fields.idFieldName)
                )
