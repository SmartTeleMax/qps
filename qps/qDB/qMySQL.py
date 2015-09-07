'''Connection class for MySQL(tm)'''

import qSQL
from qSQL import Query, Param


class Connection(qSQL.Connection):

    import MySQLdb as _db_module
    from MySQLdb import Warning, OperationalError, ProgrammingError, \
                        IntegrityError, Binary
    escape = staticmethod(_db_module.escape_string)

    DuplicateEntryError = IntegrityError

    def _is_connect_error(self, exc):
        if isinstance(exc, self.OperationalError):
            return True

    def _connect(self, *args, **kwargs):
        dbh = qSQL.Connection._connect(self, *args, **kwargs)
        dbh.autocommit(1)
        return dbh

    def queryLimits(self, limitOffset=0, limitSize=0):
        '''Return SQL representation of limits.  Used by other methods.'''
        if limitOffset or limitSize:
            return 'LIMIT %d, %d' % (limitOffset, limitSize)
        else:
            return ''

    def lastInsertID(self, table, column='id'):
        '''Return (autoincremented) ID for last INSERT command'''
        return self.execute('SELECT LAST_INSERT_ID()').fetchone()[0]

    def replace(self, table, field_dict):
        '''Construct and execute MySQL REPLACE command and return cursor.'''
        if not self._current_transaction:
            raise self.ExecuteOutsideOfTransaction()
        query = Query()
        for name, value in field_dict.items():
            if query:
                query += ','
            query += Query('%s=' % name, Param(value))
        query = 'REPLACE %s SET ' % table + query
        return self.execute(query)

    class _sql_lock:
        def __init__(self, connection, lock_string):
            self.connection = connection
            self.lock_string = lock_string
            self._locked = 0
        def acquire(self, timeout=0):
            command = 'SELECT GET_LOCK("%s", %d)' % \
                        (self.connection.escape(self.lock_string), timeout)
            self._locked = int(self.connection.execute(command).fetchone()[0])
            return self._locked
        def release(self):
            if self._locked:
                self.connection.execute('SELECT RELEASE_LOCK("%s")' % \
                                self.connection.escape(self.lock_string))
                self._locked = 0
        __del__ = release
        def __nonzero__(self):
            return self._locked

    def Lock(self, lock_string, timeout=None):
        '''Returns _sql_lock object for current connection and call its
           acquire method if timeout is specified'''
        l = self._sql_lock(self, lock_string)
        if timeout is not None:
            l.acquire(timeout)
        return l

    def begin(self):
        self.execute('BEGIN')

    def commit(self):
        self.execute('COMMIT')

    def rollback(self):
        self.execute('ROLLBACK')

# vim: ts=8 sts=4 sw=4 ai et
