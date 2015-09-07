'''Connection class for Interbase/Firebird

Notes:

1. lastInsertID method IS NOT implemented.

Interbase uses generators to get auto incremented ids, but generators
live outside of transaction control and there is no way to get next
value before insert doing gen_id(generator,1) and then get the same
value after insert by gen_id(generator,0). Generator can be already
changed by another transaction between these actions.

So, lastInsertID is just not implementable. The solution is to use special
field like described below:

class INTEGER_GEN_ID(INTEGER_AUTO_ID):
    generator = None # generator name, have to be defined!
    omitForNew = 0

    def convertFromForm(self, form, name, item=None):
        # its okay to get None value from form, it will be generated
        # a bit later
        try:
            value = FT.INTEGER_AUTO_ID.convertFromForm(self, form, name, item)
        except self.InvalidFieldContent:
            value = None
        return value

    def convertToDB(self, value, item):
        if value is None:
            # first time store, we just generate id here
            value = item.dbConn.selectRowsAsList(
                item.stream.tableName, ['gen_id(%s,1)' % self.generator],
                limitSize=1)[0][0]
            value = self.convertFromDB(value, item)
        return FT.INTEGER_AUTO_ID.convertToDB(self, value, item)

2. Interbase always returns field names in UPPERCASE.

selectRowsAsDict was redefined to convert field names back to
lowercase.  This will be fixed in the future, may be *AsDict functions
will be dropped, or they will get fields names from code.

'''

import logging
import qSQL

logger = logging.getLogger(__name__)

class Connection(qSQL.Connection):

    import kinterbasdb as _db_module
    from kinterbasdb import Warning, OperationalError, ProgrammingError, \
         IntegrityError, Binary

    def queryLimits(self, limitOffset=0, limitSize=0):
        if limitOffset or limitSize:
            return 'FIRST %d SKIP %d' % (limitSize, limitOffset)
        else:
            return ''

    def select(self, table, fields, condition='', order='', group='',
               limitOffset=0, limitSize=0):
        """Constructs and executes Interabase SELECT query in form
        SELECT FIRST m SKIP n FROM table WHERE condition..."""

        query = qSQL.Query('SELECT ')
        limits = self.queryLimits(limitOffset, limitSize)
        if limits:
            query += limits + ' '
        query += '%s FROM %s' % (','.join(fields), table)
        if condition:
            query += ' WHERE '+ condition
        if group:
            query += ' GROUP BY ' + group
        if order:
            query += ' ORDER BY ' + order
        return self.execute(query)

    def selectRowAsList(self, table, fields, condition=''):
        """Interbase reports rowcount as 0 before any fetch* calls,
        then rowcount is set to number of returned rows (but its still cant be
        more then 1302 (due to size of packet)!"""

        cursor = self.select(table, fields, condition)
        row = cursor.fetchone()
        if cursor.rowcount > 1:
            raise self.ProgrammingError('too many rows in result: %d' % \
                                                            cursor.rowcount)
        else:
            return row

    def selectRowsAsDict(self, table, fields, condition='', order='', group='',
                         limitOffset=0, limitSize=0):
        "Convert field names to lowercase"
        rows = qSQL.Connection.selectRowsAsDict(self, table, fields, condition,
                                                order, group, limitOffset,
                                                limitSize)
        return [dict([(x[0].lower(), x[1]) for x in row.items()]) \
                for row in rows]

    def begin(self, tpb=None):
        if not self.connected():
            self.connect()

        if tpb:
            self._dbh.begin(tpb)
        else:
            self._dbh.begin()

    def commit(self):
        self._dbh.commit()

    def rollback(self):
        self._dbh.rollback()
