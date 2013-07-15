# $Id: qSQL.py,v 1.14 2006/11/13 16:08:40 ods Exp $

'''Base classes for database adapters to generate SQL queries'''

import logging, weakref, time
logger = logging.getLogger(__name__)


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
        if not conn._current_transaction:
            self.impl = conn._current_transaction = TransactionImpl(conn)
            logger.debug('Transaction started')
        else:
            self.impl = conn._current_transaction
            logger.debug('Transaction reused (level=%s)', self.impl.level)
        conn._current_transaction.pushLevel()
        self.opened = 1

    def close(self):
        if self.opened:
            self.impl.popLevel()
            if not self.impl:
                self.dbConn._current_transaction = None
            self.opened = 0

    def abort(self):
        if self.opened:
            self.impl.abort()
            self.dbConn._current_transaction = None
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
        if self.level>0:
            logger.debug('Transaction level %d -> %d', self.level,
                         self.level-1)
            self.level -= 1
            if not (self.level or self.is_aborted):
                self.dbConn.commit()

    def abort(self):
        if not self.is_aborted:
            logger.debug('Transaction aborted')
            self.level = 0
            self.dbConn.rollback()
            self.is_aborted = 1

    def __nonzero__(self):
        return bool(self.level)


class Connection(object):

    _db_module = None  # Overwrite it in descending class
    _dbh = None
    _current_transaction = None
    connectHandler = None

    # timeouts in seconds to reconnect to database if connection was lost
    _reconnect_timeouts = (0, 0.5, 3)

    # redefine in subclasses to exception
    # dbmodule raises for duplicate entries
    class DuplicateEntryError(RuntimeError):
        pass

    class ExecuteOutsideOfTransaction(RuntimeError):
        pass

    class ConnectInTransaction(RuntimeError):
        pass

    def __init__(self, connection_params, charset, **kwargs):
        self.__connection_params = connection_params
        self.charset = charset
        self.__dict__.update(kwargs)

    def __del__(self):
        if self.connected():
            self._dbh.close()

    def connected(self):
        return self._dbh is not None

    def _connect(self, *args, **kwargs):
        return self._db_module.connect(*args, **kwargs)

    def connect(self):
        if not self.connected():
            if not self._current_transaction:
                logger.debug('Connecting to database')
                args, kwargs = self.__connection_params
                self._dbh = self._connect(*args, **kwargs)
                if self.connectHandler:
                    self.connectHandler(self)
            else:
                raise self.ConnectInTransaction()

    def getTransaction(self):
        return Transaction(self)

    # Don't use methods directly, use getTransaction instead
    def begin(self):
        raise NotImplementedError()
    commit = rollback = begin

    def _is_connect_error(self, exc):
        """Accepts exception (exc) occured in execute(). Returns True if
        exception indicates disconnection error"""
        raise NotImplementedError

    def executeOnce(self, query):
        '''Execute SQL command and return cursor.'''

        self.connect() # only connects if connection is closed
        cursor = self._dbh.cursor()
        logger.debug(query)
        if isinstance(query, Query):
            cursor.execute(*query.sql(self._db_module.paramstyle))
        else:
            cursor.execute(query)
        return cursor

    def execute(self, query):
        """Executes SQL command and returns curor. Tries to restore closed
        connection if self._reconnect_timeouts is not empty."""

        if self._reconnect_timeouts:
            for timeout in self._reconnect_timeouts:
                try:
                    return self.executeOnce(query)
                except Exception, exc:
                    if self._is_connect_error(exc):
                        logger.exception('Connect error in execute')
                        if self._current_transaction:
                            raise
                        self._dbh = None
                        time.sleep(timeout)
                    else:
                        raise
            else:
                raise
        else:
            return self.executeOnce(query)

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
        field_names = ','.join(field_dict.keys())
        field_values = Query(',').join(
                                    [Param(fv) for fv in field_dict.values()])
        query = 'INSERT INTO %s (%s) VALUES (' % (table, field_names) + \
                                    field_values + ')'
        return self.execute(query)

    def insertMany(self, table, fields, values):
        '''Construct and execute SQL INSERT command with executemany.

        fields is a list of field names
        values is a list of tuples of field values'''
        if not self._current_transaction:
            raise self.ExecuteOutsideOfTransaction()
        field_names = ','.join(fields)
        field_values = Query(',').join([Param(fv) for fv in values[0]])
        query = 'INSERT INTO %s (%s) VALUES (' % (table, field_names) + \
                                    field_values + ')'
        sql = query.sql(self._db_module.paramstyle)[0]
        cursor = self._dbh.cursor()
        logger.debug(sql)
        cursor.executemany(sql, values)
        return cursor

    def update(self, table, field_dict, condition=''):
        '''Construct and execute SQL UPDATE command and return cursor.'''
        if not self._current_transaction:
            raise self.ExecuteOutsideOfTransaction()
        query = Query(',').join([Query('%s=' % name, Param(value))
                                 for name, value in field_dict.items()])
        query = 'UPDATE %s SET ' % table + query
        if condition:
            query += ' WHERE '+condition
        return self.execute(query)

    def delete(self, table, condition):
        '''Construct and execute SQL DELETE command and return cursor.'''
        if not self._current_transaction:
            raise self.ExecuteOutsideOfTransaction()
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
        # It's defined as separate method so that only selectRowsAsList should
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
