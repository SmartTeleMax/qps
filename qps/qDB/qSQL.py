# $Id: qSQL.py,v 1.20 2004/03/16 15:52:48 ods Exp $

'''Base classes for database adapters to generate SQL queries'''

import logging, weakref
logger = logging.getLogger(__name__)

from mx import DateTime


class WrongType(TypeError):
    '''Raised when unknown type is used'''
    def __init__(self, value_type):
        self.value_type = value_type
    def __str__(self):
        return 'Cannot represent object of type %s in SQL query' % \
               self.value_type.__name__


class Raw:
    '''Base class for types that know how to represent itself in SQL
    (convert method).'''
    def __init__(self, sql_repr):
        self.sql_repr = sql_repr
    def convert(self):
        return self.sql_repr
    def __repr__(self):
        return '<%s(%s)>' % (self.__class__.__name__, self.sql_repr)


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
        if self._dbh is not None:
            self._dbh.close()

    def _connect(self, *args, **kwargs):
        return self._db_module.connect(*args, **kwargs)

    def connect(self):
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
        assert type(fields) is not str  # Catch common error
        query_parts = ['SELECT %s FROM %s' % (','.join(fields), table)]
        if condition:
            query_parts.append('WHERE '+condition)
        if group:
            query_parts.append('GROUP BY '+group)
        if order:
            query_parts.append('ORDER BY '+order)
        if limitOffset or limitSize:
            query_parts.append(self.queryLimits(limitOffset, limitSize))
        return self.execute(' '.join(query_parts))

    def insert(self, table, field_dict):
        '''Construct and execute SQL INSERT command and return cursor.'''
        field_names = []
        field_values = []
        for field_name, field_value in field_dict.items():
            field_names.append(field_name)
            field_values.append(self.convert(field_value))
        query = 'INSERT INTO %s (%s) VALUES (%s)' % \
                    (table, ','.join(field_names), ','.join(field_values))
        return self.execute(query)

    def update(self, table, field_dict, condition=''):
        '''Construct and execute SQL UPDATE command and return cursor.'''
        updates = ', '.join(['%s=%s' % (fn, self.convert(fv))
                             for fn, fv in field_dict.items()])
        query = 'UPDATE %s SET %s' % (table, updates)
        if condition:
            query += ' WHERE '+condition
        return self.execute(query)

    def delete(self, table, condition):
        '''Construct and execute SQL DELETE command and return cursor.'''
        query = 'DELETE FROM '+table
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

    def convert(self, value):
        '''Return string representing value in SQL query.'''
        value_type = type(value)
        if value is None:
            return 'NULL'
        elif value_type is DateTime.DateTimeType:
            return "'%s'" % value.strftime('%Y-%m-%d %H:%M:%S')
        elif value_type is str:
            return "'%s'" % self.escape(value)
        elif value_type is unicode:
            return "'%s'" % self.escape(str(value))
        elif value_type in (int, long, float):
            return str(value)
        elif isinstance(value, Raw):
            return value.convert()
        else:
            raise WrongType(value_type)

    def updateLU(self, table, condition, field='_qps_lu', ts=Raw('NOW()')):
        return self.update(table, {field: ts}, condition)

    # Bind to Connection namespace
    WrongType = WrongType
    Raw = Raw

    def IN(self, field_name, values):
        if values:
            if len(values)==1:
                return '%s=%s' % (field_name, self.convert(values[0]))
            else:
                return '%s IN (%s)' % (field_name,
                                       ','.join(map(self.convert, values)))
        else:
            return '0'

    def NOT_IN(self, field_name, values):
        if not values:
            return '1'
        elif len(values)==1:
            return '%s!=%s' % (field_name, self.convert(values[0]))
        else:
            return '%s NOT IN (%s)' % (field_name,
                                       ','.join(map(self.convert, values)))

    def join(self, exprs, joiner='AND'):
        assert type(exprs) is not str  # Catch common error
        exprs = filter(None, exprs)
        if not exprs:
            return ''
        elif len(exprs)==1:
            return exprs[0]
        else:
            return joiner.join(['('+expr+')' for expr in exprs])

# vim: ts=8 sts=4 sw=4 ai et
