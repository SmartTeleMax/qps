# $Id: $
from qps.qUtils import DictRecord
from qps.qVirtual import CommonVirtualStream


streamDescriptions = {

    'rubrics': DictRecord(
        title='Rubrics',
        streamClass='qps.qBricks.qStatic.StaticStream',
        itemListSpec=[
            ('id1', {'title': 'First rybric title'}),
            ('id2', {'title': 'Second rubric title'}),
        ],
        streamMakers=['qps.qMake.ItemsMaker'],
        itemMakers=['qps.qMake.VirtualsMaker'],
        permissions=[('all', 'rx')]),

    'docs': DictRecord(
        title='Documents',
        tableName='docs',
        condition='',  # raw SQL condition to place into WHERE clause
        order='id',
        indexNum=10,   # number of items on page
        streamCat='docs',
        streamClass='qps.qBricks.qSQL.SQLStream',
        permissions=[('editors', 'rwxcd'), ('all', 'rx')]),

}

virtualStreamRules = [

    CommonVirtualStream('docs', 'rubrics', 'rubric',
                        streamParams=DictRecord(
                            streamMakers=['qps.qMake.ItemsMaker',
                                          'qps.qMake.Maker'],
                            itemMakers=['qps.qMake.Maker'])),

]
