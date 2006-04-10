'''Connection class for Oracle v0.4'''

import qSQL
import logging
logger=logging.getLogger(__name__)

class Connection(qSQL.Connection):

    import cx_Oracle as _db_module
    from cx_Oracle import Warning, OperationalError, ProgrammingError, \
                        IntegrityError#, Binary
#   escape = staticmethod(_db_module.escape_string)

    DuplicateEntryError = IntegrityError

    def _connect(self, *args, **kwargs):
	from os import environ
	environ['ORACLE_HOME']=kwargs['orahome']
	conn=self._db_module.connect(kwargs['user'],kwargs['passwd'],self._db_module.makedsn(kwargs['host'],1521,kwargs['db']))
	return conn
    
    def selectRowAsList(self,table,fields,condition=''):
	cursor=self.select(table,fields,condition)
	return cursor.fetchone()

    def select(self, table, fields, condition='', order='', group='',
                   limitOffset=0, limitSize=0):
	'''Construct and execute SQL query and return cursor.'''
        assert type(fields) is not str   # Catch common error
	query = qSQL.Query('SELECT %s FROM %s' % (','.join(fields), table))
        if limitOffset or limitSize:
    	    if condition:
    		condition += ' AND '
    	    condition += self.queryLimits(limitOffset, limitSize)
        if condition:
    	    query += ' WHERE ' + condition
        if group:
    	    query += ' GROUP BY ' + group
	if order:
    	    query += ' ORDER BY ' + order
#        logger.info(query)
        return self.execute(query)
    
    def queryLimits(self,limitOffset=0,limitSize=0):
	if limitOffset or limitSize:
	    return 'ROWNUM BETWEEN %d and %d' % (limitOffset+1,limitOffset+limitSize)
	else:
	    return ''
	    
    def selectRowsAsDict(self, table, fields, condition='', order='', group='',
                             limitOffset=0, limitSize=0):
        cursor = self.select(table, fields, condition, order, group,
            			 limitOffset, limitSize)
        result = cursor.fetchall()
        if result:
    	    names = [fd[0].lower() for fd in cursor.description]
    	    return [dict(zip(names, row)) for row in result]
        else:
    	    return []
                                                                                                                                              
    def selectRowAsDict(self, table, fields, condition=''):
	cursor = self.select(table, fields, condition)
        names = [fd for fd in fields]
        return dict(zip(names, cursor.fetchone()))

        
    def setTransType(self,trans_type):
	self._db_module.execute('SET TRANSACTION %s' % trans_type)

    def lastInsertID(self, table, column='id'):
	'''Return (autoincremented) ID for last INSERT command'''
	return self.execute('SELECT max('+column+') FROM '+table).fetchone()[0]
                   
    def insert(self, table, field_dict):
	'''Construct and execute SQL INSERT command and return cursor.'''
	field_names = []
        field_values = []
        for field_name, field_value in field_dict.items():
            if field_names:
                field_names.append(',')
                field_values.append(',')
    	    field_names.append(field_name)
    	    if not field_value:
    		field_value=''
    	    field_values.append(qSQL.Param(field_value))
        query = 'INSERT INTO %s (' % table + qSQL.Query(*field_names) + \
                                    ') VALUES (' + qSQL.Query(*field_values) + ')'
        return self.execute(query)
    
    def insertMany(self, table, fields, values):
        '''Construct and execute SQL INSERT command with executemany.
        fields is a list of field names
        values is a list of tuples of field values'''
        if not self._current_transaction:
            raise self.ExecuteOutsideOfTransaction()
        field_names = ','.join(fields)
        field_values = []
        
        for value in values[0]:
            if field_values:
                field_values.append(',')
            if not value:
        	value=''
            field_values.append(Param(value))
        query = 'INSERT INTO %s (%s) VALUES (' % (table, field_names) + \
                Query(*field_values) + ')'
        query = query.sql(self._db_module.paramstyle)[0]
                                                                                                                                                
        cursor = self._dbh.cursor()
        cursor.executemany(query, values)
        return cursor
                                                                                                                                                                                        
    def begin(self):
	self._dbh.begin()

    def commit(self):
	self._dbh.commit()
	
    def rollback(self):
	self._dbh.rollback()

                                                                                                                                                                                                                                                                                                                            
# vim: ts=8 sts=4 sw=4 ai et
