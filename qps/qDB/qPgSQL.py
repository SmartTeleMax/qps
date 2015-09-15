# $Id: qPgSQL.py,v 1.2 2006/02/23 23:04:54 corva Exp $

'''Connection class for PosgreSQL'''

import qSQL


try:
    import pyPgSQL
except:
    use_pyPgSQL = 0
else:
    use_pyPgSQL = 1


class Connection(qSQL.Connection):

    if use_pyPgSQL:
        from pyPgSQL import PgSQL as _db_module
        # We need this hack since convert won't work with instances
        _db_module.PgInt8 = _db_module.PgInt8Type = long
        from pyPgSQL.PgSQL import Warning, OperationalError, ProgrammingError, \
                                  IntegrityError

        def escape(self, s):
            return self._db_module.PgQuoteString(s)[1:-1]

    else:
        import pgdb as _db_module
        from pgdb import Warning, OperationalError, ProgrammingError

        def escape(self, s):
            return self._db_module._quote(s)[1:-1]

    DuplicateEntryError = OperationalError

    _db_module.fetchReturnsList = 1
    Binary = str

    def _connect(self, *args, **kwargs):
        self._dbh = self._db_module.connect(*args, **kwargs)
        self._dbh.autocommit = 1

    def begin(self):
        self.execute('BEGIN')

    def commit(self):
        self.execute('COMMIT')

    def rollback(self):
        self.execute('ROLLBACK')

    def selectRowAsList(self, table, fields, condition=''):
        '''Retrieve one row as list. It's an error when contains more than one
        row.'''
        cursor = self.select(table, fields, condition)
        # Walkaround for bug in pyPgSQL
        return cursor.fetchone()

    def selectRowAsDict(self, table, fields, condition=''):
        '''Retrieve one row as dictionary. It's an error when contains more
        than one row.'''
        cursor = self.select(table, fields, condition)
        row = cursor.fetchone()
        if row is None:
            return
        else:
            names = [fd[0] for fd in cursor.description]
            return dict(zip(names, row))

    def lastInsertID(self, table, column='id'):
        '''Return (autoincremented) ID for last INSERT command'''
        query = "SELECT CURRVAL('%s_%s_seq')" % (table, column)
        return self.execute(query).fetchone()[0]

# vim: ts=8 sts=4 sw=4 ai et
