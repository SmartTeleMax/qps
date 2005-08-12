# $Id: qFilters.py,v 1.2 2005/08/08 11:37:37 corva Exp $

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
                    filterFieldClass=SQL_LIKE_STRING))
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
                getattr(type, 'filterFieldClass', False)]

    def createField(self, field):
        "Returns FilterFieldType for field object"
        return field.filterFieldClass.create(field)
    
    def createStream(self, stream, loader, method="AND"):
        """Returns an instance of stream with applied filter params"""


class SQLStreamFilter(StreamFilter):
    """Filter for SQL streams, operates with conditions and joinTemplates"""
    
    def __init__(self):
        self.conditions = []
        self.joinTemplates = []

    def __nonzero__(self):
        return bool(self.conditions or self.joinTemplates)

    def createStream(self, stream, loader, cond_method="AND"):
        jt = getattr(stream, "joinTemplate", "%(brick.tableName)s")
        jt = ' '.join([jt]+self.joinTemplates)
        stream = loader(stream.id, joinTemplate=jt)
        stream.addToCondition(stream.dbConn.join(self.conditions, cond_method))
        return stream


#
# Filter field types classes
#

import qps.qFieldTypes as FT

class FilterFieldType:
    @ classmethod
    def create(cls, field):
        """Returns a new instance of filter field initialized with required
        params from field"""
        return cls(title=field.title)
    
    def applyToFilter(self, filter, item, name, value):
        """Changes filter state"""


#
# Conditions
#

from qps.qDB.qSQL import Query, Param

class SQLEquals:
    def applyToFilter(self, filter, item, name, value):
        filter.conditions.append(
            Query("%s.%s=" % (item.stream.tableName, name),
                  Param(self.convertToDB(value, item)))
            )
        

class SQLLikes:
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

    @ classmethod
    def create(cls, field):
        return cls(title=field.title, stream=field.stream)


class SQL_EXT_FOREIGN_MULTISELECT(FilterFieldType, FT.FOREIGN_DROP):
    extraOption = " "

    @ classmethod
    def create(cls, field):
        return cls(title=field.title, stream=field.stream, orig=field)
        
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
