# $Id: qPath.py,v 1.7 2005/08/06 00:39:33 corva Exp $

'''Standard QPS path parser'''

import logging
logger = logging.getLogger(__name__)


from qSite import StreamNotFoundError


class PathParser:

    def __init__(self, site, item_extensions=('html',),
                 index_file='index'):
        self.site = site
        self.item_extensions = item_extensions
        self.index_file = index_file

    def __call__(self, path, retrieve_stream=None):
        '''Return chain of matched objects.'''
        if retrieve_stream is None:
            retrieve_stream = self.site.retrieveStream
        if path in ('', '/'):
            return (self.site,)
        elif path[0]!='/':
            return (None,)
        elif path.endswith('/'):
            try:
                return (self.site, retrieve_stream(path[1:-1]))
            except StreamNotFoundError:
                return (self.site, None)
        else:
            pos = path.rfind('/')
            if pos<=0:
                return (self.site, None)
            try:
                stream = retrieve_stream(path[1:pos])
            except StreamNotFoundError:
                return (self.site, None, None)
            item_path = path[pos+1:]
            pos = item_path.rfind('.')
            if pos>=0 and (item_path[pos+1:] in self.item_extensions):
                item_id = item_path[:pos]
            else:
                item_id = item_path
            if item_id==self.index_file:
                return (self.site, stream)
            try:
                item_id = stream.fields.id.convertFromString(item_id)
            except:
                return (self.site, stream, None)
            return (self.site, stream, stream.retrieveItem(item_id))


class PagedStreamLoader:

    def __init__(self, site, form, **params):
        self.site = site
        self.form = form
        self.params = params

    def __call__(self, stream_id, **params):
        try:
            page = int(self.form.getfirst('page', 1))
        except ValueError:
            page = 1
        if page<=0:
            page = 1
        _params = self.params.copy()
        _params.update(params)
        return self.site.createStream(stream_id, page=page, **_params)


class FilteredStreamLoader(PagedStreamLoader):

    class PrefixForm:
        def __init__(self, form, prefix):
            self.form = form
            self.prefix = prefix
            
        def getString(self, key, default=None):
            return self.form.getString(self.prefix+key, default)
        
        def getStringList(self, key):
            return self.form.getStringList(self.prefix+key)
        
        def getfirst(self, key, default=None):
            return self.form.getfirst(self.prefix+key, default)
        
        def getlist(self, key):
            return self.form.getlist(self.prefix+key)
    
    def __call__(self, stream_id, **params):
        stream = PagedStreamLoader.__call__(self, stream_id, **params)
        if hasattr(stream, 'filter'):
            filter = stream.filter.__class__()
            state = stream.createNewItem()
            state.stream = stream
            names = filter.fields(stream)
            method = "AND" # no functionality to define method at the moment
            form = self.PrefixForm(self.form, 'filter-')
            for name in names:
                field = filter.createField(stream.fields[name])
                value = field.convertFromForm(form, name, state)
                setattr(state, name, value)
                if value:
                    field.applyToFilter(filter, state, name, value)
            if filter:
                stream = filter.createStream(
                    stream, PagedStreamLoader(self.site, self.form), method)
                stream.filterState = state # XXX need to store somethere
        return stream
    
# vim: ts=8 sts=4 sw=4 ai et
