'''QPS system

Connection class for PosgreSQL

$Id: qPgSQL.py,v 1.7 2003/05/31 12:52:38 ods Exp $
'''

import qSQL


class Connection(qSQL.Connection):

    import pgdb as _db_module
    from pgdb import Warning, OperationalError, ProgrammingError

    def escape(self, s):
        return self._db_module._quote(s)[1:-1]

    Binary = str

    def _connect_and_execute(self, query):
        args, kwargs = self.__connection_params
        self._dbh = self._db_module.connect(*args, **kwargs)
        self._dbh.autocommit = 1
        del self.execute
        return self.execute(query)

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
