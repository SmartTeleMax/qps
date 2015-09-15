import qSQL

class Connection(qSQL.Connection):

    import pysqlite2.dbapi2 as _db_module
    from pysqlite2.dbapi2 import Warning, OperationalError, ProgrammingError, \
                                 IntegrityError, Binary

    DuplicateEntryError = IntegrityError

    def queryLimits(self, limitOffset=0, limitSize=0):
        '''Return SQL representation of limits.  Used by other methods.'''
        if limitOffset or limitSize:
            return 'LIMIT %d, %d' % (limitOffset, limitSize)
        else:
            return ''

    def selectRowAsList(self, table, fields, condition=''):
        rows = self.selectRowsAsList(table, fields, condition='')
        if not rows:
            return
        if len(rows) > 1:
            raise self.ProgrammingError('too many rows in result: %d' %
                                                                    len(rows))
        return rows[0]

    def selectRowAsDict(self, table, fields, condition=''):
        rows = self.selectRowsAsDict(table, fields, condition='')
        if not rows:
            return
        if len(rows) > 1:
            raise self.ProgrammingError('too many rows in result: %d' %
                                                                    len(rows))
        return rows[0]

    def lastInsertID(self, table, column='id'):
        return self.execute('select last_insert_rowid()').fetchone()[0]

    def begin(self):
        # sqlite starts transactions automatically
        self.connect()

    def commit(self):
        if self._dbh is not None:
            self._dbh.commit()

    def rollback(self):
        if self._dbh is not None:
            self._dbh.rollback()


# generating triggers

fk_id = '%(child_table)s_%(child_column)s'

# insert and update triggers

# foreign key not null
notexist_condition = '''((SELECT %(parent_column)s FROM %(parent_table)s
                WHERE %(parent_column)s = new.%(child_column)s)
               IS NULL)'''

# foreign key may be null
notnull_and_notexist_condition = '''((new.%(child_column)s IS NOT NULL)
          AND ''' + notexist_condition + ')'

insert_trigger = '''
CREATE TRIGGER fki_%(fk_id)s
BEFORE INSERT ON %(child_table)s
FOR EACH ROW
    WHEN %(condition)s
BEGIN
    SELECT RAISE(ABORT, 'insert on table "%(child_table)s" violates foreign key constraint on column "%(child_column)s"');
END;
'''

update_trigger = '''
CREATE TRIGGER fku_%(fk_id)s
BEFORE UPDATE ON %(child_table)s
FOR EACH ROW
    WHEN %(condition)s
BEGIN
    SELECT RAISE(ABORT, 'update on table "%(child_table)s" violates foreign key constraint on column "%(child_column)s"');
END;
'''

# delete triggers

_is_child = '%(child_column)s = old.%(parent_column)s'

del_restrict = '''
CREATE TRIGGER fkd_%(fk_id)s
BEFORE DELETE ON %(parent_table)s
FOR EACH ROW
    WHEN ((SELECT %(child_column)s FROM %(child_table)s
           WHERE '''  + _is_child + ''')
          IS NOT NULL)
BEGIN
    SELECT RAISE(ABORT, 'delete on table "%(parent_table)s" violates foreign key constraint on table "%(child_table)s" column "%(child_column)s"');
END;
'''

del_cascade = '''
CREATE TRIGGER fkd_%(fk_id)s
BEFORE DELETE ON %(parent_table)s
FOR EACH ROW BEGIN
    DELETE from %(child_table)s WHERE ''' + _is_child + ''';
END;
'''

del_null = '''
CREATE TRIGGER fkd_%(fk_id)s
BEFORE DELETE ON %(parent_table)s
FOR EACH ROW BEGIN
    UPDATE %(child_table)s set %(child_column)s=NULL WHERE ''' + _is_child +''';
END;
'''


def make_triggers(table, col, parent_table, parent_col='id',
                         not_null=False, on_delete='restrict'):
    ''' Generates a list of CREATE TRIGGER statements that can be used
        to emulate a foreign key on <table.col> referencing
        <parent_table.parent_col>.
        No trigger fires on update of a primary key -don't do that '''
    names = {
        'child_table': table,
        'child_column': col,
        'parent_table': parent_table,
        'parent_column': parent_col,
    }
    names['fk_id'] = fk_id % names

    # insert and update triggers
    if not_null:
        condition = notexist_condition
    else:
        condition = notnull_and_notexist_condition
    names1 = names.copy()
    names1['condition'] = condition % names
    insert = insert_trigger % names1
    update = update_trigger % names1

    # delete trigger
    trigger = globals()['del_%s' % on_delete]
    delete = trigger % names

    return (insert, update, delete)
