from qps.qMake import *
import qps.qWebUtils, qps.qUtils

class TOCMaker(Maker):
    name = 'toc'
    extention = 'html'
    
    def path(self, brick):
        path = brick.path()
        if path[-1:]=='/':
            path = "%s_%s.%s" % (path, self.name, self.extention)
        return path

    def getTemplateName(self, brick):
        template_name = Maker.getTemplateName(self, brick)
        return '/'.join([self.name, template_name])

class SearchIndexMaker(Maker):
    def sqlCondition(self, brick):
        dbConn = brick.dbConn
        return "(brick_id=%s) AND (stream_id=%s)" % (
            dbConn.convert(brick.id),
            dbConn.convert(brick.stream.canonical_id))
    
    def do_delete(self, brick):
        import Search
        brick.dbConn.delete(Search.tableName, self.sqlCondition(brick))
    
    def do_make(self, brick):
        import Search
        text = Search.Text(Search.getBrickText(brick))
        words = text.getwords()

        self.do_delete(brick)
        for word in words:
            if brick.site.dbCharset:
                word = word.encode(brick.site.dbCharset)
            try:
                brick.dbConn.insert(Search.tableName,
                                    {'brick_id': brick.id,
                                     'stream_id': brick.stream.canonical_id,
                                     'word': word})
            except brick.dbConn.DuplicateEntryError:
                pass
