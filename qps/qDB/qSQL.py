# $Id: qSQL.py,v 1.3 2004/07/05 10:38:23 corva Exp $

'''Base classes for database adapters to generate SQL queries'''

import logging, weakref
logger = logging.getLogger(__name__)

from mx import DateTime


class Raw:
    "Raw query parameter"
    
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return 'Raw(%r)' % (self.value,)


class Param(object):
    "Query parameter"

    def __new__(cls, value):
        if isinstance(value, Raw):
            return value.value
        else:
            self = object.__new__(cls)
            self.value = value
            return self
    def __repr__(self):
        return 'Param(%r)' % (self.value,)


class Query(object):
    """SQL query object. Represents SQL query and can be converted to any
    Python DB API 2.0 format.

    Usage:

        query = Query('id=', Param(10))
        query += ' AND ' + Query('date>', Param(datetimeobject)) + \
        ' AND published=' + Param('y')
        

        Query(' AND ').join(query_parts)

        query.sql(paramstyle)"""

    def __init__(self, *args):
        self.chunks = list(args)

    def __repr__(self):
        return ''.join([type(c) is str and c or repr(c) for c in self.chunks])
    __str__ = __repr__

    def __nonzero__(self):
        return len(self.chunks) > 0

    def __add__(self, other):
        if isinstance(other, Query):
            return Query(*(self.chunks + other.chunks))
        else:
            return Query(*(self.chunks+[other]))

    def __radd__(self, other):
        if isinstance(other, Query):
            return Query(*(other.chunks+self.chunks))
        else:
            return Query(*([other]+self.chunks))

    def join(self, queries):
        result = Query()
        for query in queries:
            if result:
                result += self
            result += query
        return result

    def sql(self, paramstyle):
        return getattr(self, "to_%s" % paramstyle)()

    def to_qmark(self):
        query_parts = []
        params = []
        for chunk in self.chunks:
            if isinstance(chunk, Param):
                params.append(chunk.value)
                query_parts.append('?')
            else:
                query_parts.append(chunk)
        return ''.join(query_parts), params

    def to_numeric(self):
        query_parts = []
        params = []
        for chunk in self.chunks:
            if isinstance(chunk, Param):
                params.append(chunk.value)
                query_parts.append(':%d' % len(params))
            else:
                query_parts.append(chunk)

        # DCOracle2 has broken support for sequences of other types
        return ''.join(query_parts), tuple(params)

    def to_named(self):
        query_parts = []
        params = {}
        for chunk in self.chunks:
            if isinstance(chunk, Param):
                name = 'p%d' % len(params)  # Are numbers in name allowed?
                params[name] = chunk.value
                query_parts.append(':%s' % name)
            else:
                query_parts.append(chunk)
        return ''.join(query_parts), params

    def to_format(self):
        query_parts = []
        params = []
        for chunk in self.chunks:
            if isinstance(chunk, Param):
                params.append(chunk.value)
                query_parts.append('%s')
            else:
                query_parts.append(chunk.replace('%', '%%'))
        return ''.join(query_parts), params

    def to_pyformat(self):
        query_parts = []
        params = {}
        for chunk in self.chunks:
            if isinstance(chunk, Param):
                name = '%d' % len(params)
                params[name] = chunk.value
                query_parts.append('%%(%s)s' % name)
            else:
                query_parts.append(chunk.replace('%', '%%'))
        return ''.join(query_parts), params


class Transaction:

    def __init__(self, conn):
        self.dbConn = conn
        if not hasattr(conn, '_current_transaction'):
            conn._current_transaction = TransactionImpl(conn)
        conn._current_transaction.pushLevel()
        self.opened = 1

    def close(self):
        self.dbConn._current_transaction.popLevel()
        self.opened = 0

    def abort(self):
        if self.opened:
            self.dbConn._current_transaction.abort()
            self.opened = 0
    __del__ = abort


class TransactionImpl:

    def __init__(self, conn):
        self.dbConn = conn
        self.level = 0
        self.is_aborted = 0

    def pushLevel(self):
        logger.debug('Transaction level %d -> %d', self.level, self.level+1)
        if not self.level:
            self.dbConn.begin()
        self.level += 1

    def popLevel(self):
        assert self.level>0
        logger.debug('Transaction level %d -> %d', self.level, self.level-1)
        self.level -= 1
        if not (self.level or self.is_aborted):
            self.dbConn.commit()

    def abort(self):
        if not self.is_aborted:
            self.dbConn.rollback()
            self.is_aborted = 1


class Connection(object):

    __connections_cache = weakref.WeakValueDictionary()
    _db_module = None  # Overwrite it in descending class
    _dbh = None

    def __new__(cls, *args, **kwargs):
        cache_key = (cls, args, tuple(kwargs.items()))
        if not cls.__connections_cache.has_key(cache_key):
            self = object.__new__(cls)
            self.__connection_params = (args, kwargs)
            self.execute = self._connect_and_execute
            cls.__connections_cache[cache_key] = self
        return cls.__connections_cache[cache_key]

    def __del__(self):
        if self.connected():
            self._dbh.close()

    def connected(self):
        return self._dbh is not None

    def _connect(self, *args, **kwargs):
        return self._db_module.connect(*args, **kwargs)

    def connect(self):
        if not self.connected():
            args, kwargs = self.__connection_params
            self._dbh = self._connect(*args, **kwargs)

    def _connect_and_execute(self, query):
        self.connect()
        del self.execute
        return self.execute(query)

    def getTransaction(self):
        return Transaction(self)

    # Don't use methods directly, use getTransaction instead
    def begin(self):
        pass
    commit = rollback = begin
    
    def execute(self, query):
        '''Execute SQL command and return cursor.'''
        cursor = self._dbh.cursor()
        logger.debug(query)
        if isinstance(query, Query):
            cursor.execute(*query.sql(self._db_module.paramstyle))
        else:
            cursor.execute(query)
        return cursor

    def queryLimits(self, limitOffset=0, limitSize=0):
        '''Return SQL representation of limits.  Used by other methods.'''
        if limitOffset or limitSize:
            return 'LIMIT %d OFFSET %d' % (limitSize, limitOffset)
        else:
            return ''

    def select(self, table, fields, condition='', order='', group='',
               limitOffset=0, limitSize=0):
        '''Construct and execute SQL query and return cursor.'''
        assert type(fields) is not str   # Catch common error
        query = Query('SELECT %s FROM %s' % (','.join(fields), table))
        if condition:
            query += ' WHERE ' + condition
        if group:
            query += ' GROUP BY ' + group
        if order:
            query += ' ORDER BY ' + order
        if limitOffset or limitSize:
            query += ' ' + self.queryLimits(limitOffset, limitSize)
        return self.execute(query)

    def insert(self, table, field_dict):
        '''Construct and execute SQL INSERT command and return cursor.'''
        field_names = []
        field_values = []
        for field_name, field_value in field_dict.items():
            if field_names:
                field_names.append(',')
                field_values.append(',')
            field_names.append(field_name)
            field_values.append(Param(field_value))
        query = 'INSERT INTO %s (' % table + Query(*field_names) + \
                ') VALUES (' + Query(*field_values) + ')'
        return self.execute(query)

    def insertMany(self, table, fields, values):
        '''Construct and execute SQL INSERT command with executemany.

        fields is a list of field names
        values is a list of tuples of field values'''
        field_names = ','.join(fields)
        field_values = []

        for value in values[0]:
            if field_values:
                field_values.append(',')
            field_values.append(Param(value))
        query = 'INSERT INTO %s (%s) VALUES (' % (table, field_names) + \
                Query(*field_values) + ')'
        query = query.sql(self._db_module.paramstyle)[0]

        cursor = self._dbh.cursor()
        logger.debug(query)
        cursor.executemany(query, values)
        return cursor

    def update(self, table, field_dict, condition=''):
        '''Construct and execute SQL UPDATE command and return cursor.'''
        query = Query()
        for name, value in field_dict.items():
            if query:
                query += ','
            query += Query('%s=' % name, Param(value))
        query = 'UPDATE %s SET ' % table + query

        if condition:
            query += ' WHERE '+condition
        return self.execute(query)

    def delete(self, table, condition):
        '''Construct and execute SQL DELETE command and return cursor.'''
        query = Query('DELETE FROM '+table)
        if condition:
            query += ' WHERE '+condition
        return self.execute(query)

    # Handy select variants
    def selectRowsAsList(self, table, fields, condition='', order='', group='',
                         limitOffset=0, limitSize=0):
        '''Return sequence of rows, represented as lists.'''
        cursor = self.select(table, fields, condition, order, group,
                             limitOffset, limitSize)
        return cursor.fetchall()

    def selectRows(self, *args, **kwargs):
        '''Alias for selectRowsAsList().'''
        # It's define as separate method so that only selectRowsAsList should
        # be overwritten when needed.
        return self.selectRowsAsList(*args, **kwargs)

    def selectRowAsList(self, table, fields, condition=''):
        '''Retrieve one row as list. Its an error when contains more than one
        row.'''
        cursor = self.select(table, fields, condition)
        if not cursor.rowcount:
            return
        elif cursor.rowcount==1:
            return cursor.fetchone()
        else:
            raise self.ProgrammingError('too many rows in result: %d' % \
                                                            cursor.rowcount)

    def selectRow(self, *args, **kwargs):
        '''Alias for selectRowAsList().'''
        # It's define as separate method so that only selectRowAsList should
        # be overwritten when needed.
        return self.selectRowAsList(*args, **kwargs)

    def selectFieldAsList(self, table, field, condition='', order='', group='',
                          limitOffset=0, limitSize=0):
        '''Retrieve values of single field.'''
        cursor = self.select(table, [field], condition, order, group,
                             limitOffset, limitSize)
        return [row[0] for row in cursor.fetchall()]

    def selectField(self, table, field, condition=''):
        '''Retrieve single value of single field.'''
        return self.selectRow(table, [field], condition)[0]

    def selectRowsAsDict(self, table, fields, condition='', order='', group='',
                         limitOffset=0, limitSize=0):
        '''Return sequence of rows, represented as dictionaries.'''
        cursor = self.select(table, fields, condition, order, group,
                             limitOffset, limitSize)
        result = cursor.fetchall()
        if result:
            names = [fd[0] for fd in cursor.description]
            return [dict(zip(names, row)) for row in result]
        else:
            return []

    def selectRowAsDict(self, table, fields, condition=''):
        '''Retrieve one row as dictionary. Its an error when contains more
        than one row.'''
        cursor = self.select(table, fields, condition)
        if not cursor.rowcount:
            return
        elif cursor.rowcount==1:
            names = [fd[0] for fd in cursor.description]
            return dict(zip(names, cursor.fetchone()))
        else:
            raise self.ProgrammingError('too many rows in result: %d' % \
                                                            cursor.rowcount)

    def lastInsertID(self, table, column='id'):
        '''Return (autoincremented) ID for last INSERT command'''
        raise NotImplementedError('lastInsertID()')

    def escape(self, string):
        raise NotImplementedError('escape()')

    def updateLU(self, table, condition, field='_qps_lu', ts=Raw('NOW()')):
        return self.update(table, {field: ts}, condition)

    def IN(self, field_name, values):
        if values:
            if len(values)==1:
                return Query('%s=' % field_name, Param(values[0]))
            else:
                return '%s IN (' % field_name + \
                       Query(',').join([Param(x) for x in values]) + ')'
        else:
            return '0'

    def NOT_IN(self, field_name, values):
        if not values:
            return '1'
        elif len(values)==1:
            return Query('%s!=' % field_name, Param(values[0]))
        else:
            return '%s NOT IN (' % field_name + \
                       Query(',').join([Param(x) for x in values]) + ')'

    def join(self, exprs, joiner=' AND '):
        assert type(exprs) is not str  # Catch common error
        if not isinstance(joiner, Query):
            joiner = Query(joiner)
        exprs = filter(None, exprs)
        if not exprs:
            return ''
        elif len(exprs)==1:
            return exprs[0]
        else:
            return joiner.join(['('+expr+')' for expr in exprs])

# vim: ts=8 sts=4 sw=4 ai et
