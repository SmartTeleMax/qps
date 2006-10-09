# $Id: qPath.py,v 1.12 2006/10/04 15:56:21 corva Exp $

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
                item_id = stream.fields.id.convertFromString(item_id,
                                                             self.site)
            except:
                return (self.site, stream, None)
            return (self.site, stream, stream.retrieveItem(item_id))


class StreamLoaderPlugin:
    """Plugin interface for fetching stream information from form"""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def applyToStream(self, site, form, stream):
        """Accepts site object (site), form object (form)
        and stream creation params as dict (params).

        May extract stream information from form, and modify and return
        params"""

        return stream

    def applyToParams(self, site, form, params):
        """Accepts site object (site), form object (form)
        and stream object (stream).

        May extract stream information from form,
        then modify and return the stream"""

        return params
        

class Page(StreamLoaderPlugin):
    """Extracts stream.page information from form"""
    
    paramName = 'page'
    
    def applyToParams(self, site, form, params):
        try:
            page = int(form.getfirst(self.paramName, 1))
        except ValueError:
            page = 1
        if page <= 0:
            page = 1
        params['page'] = page
        return params


class Tag(StreamLoaderPlugin):
    """Extracts stream.tag information from form"""

    paramName = 'tag'

    def applyToParams(self, site, form, params):
        tag = form.getfirst('tag', None)
        params['tag'] = tag
        return params
        

class Order(StreamLoaderPlugin):
    """Extracts stream.order information from form"""
    
    fieldName = 'order_field'
    directionName = 'order_direction'

    def applyToStream(self, site, form, stream):
        fieldname = form.getfirst(self.fieldName, None)
        defaultOrder = stream.getFieldOrder(fieldname)
        if fieldname is not None:
            direction = form.getfirst('order_direction',
                                      defaultOrder).upper()
        if defaultOrder and direction in ('ASC', 'DESC'):
            stream.order = ((fieldname, direction),)
        return stream


class Filter(StreamLoaderPlugin):
    """Extracts filtering information from form using 'prefix' keyword
    for filter parameters"""
    
    prefix = "filter-"
    
    class PrefixForm:
        """Emulates qHTTP.FieldStorage interface, proxies access to
        FieldStorage data using prefixed names"""
        
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
    
    def applyToStream(self, site, form, stream):
        if hasattr(stream, 'filter'):
            filter = stream.filter.__class__()
            state = filter.createState(stream)
            state.stream = stream
            names = filter.fields(stream)
            method = "AND" # no functionality to define method at the moment
            form = self.PrefixForm(form, self.prefix)
            for name in names:
                field = filter.createField(stream.fields[name])
                value = field.convertFromForm(form, name, state)
                setattr(state, name, value)
                if value:
                    field.applyToFilter(filter, state, name, value)
            if filter:
                stream = filter.applyToStream(stream, method)
                stream.filterState = state # XXX need to store somethere
        return stream


class StreamLoader:
    """StreamLoader emulates qSite.Site.createStream interface by it's
    __call__ method. You initialize StreamLoader to gather stream's params
    from web request, represented by qHTTP.FieldStorage.

    def webmethod(site, form):
        loader = StreamLoader(site, form, plugins=[Page()])
        loader('stream_id', indexNum=10)

    loader call in webmethod is equivalent to site.createStream, but page is
    initialized by Page plugin from 'page' parameter of form."""
    
    def __init__(self, site, form, plugins=[], **params):
        self.site = site
        self.form = form
        self.params = params
        self.plugins = plugins

    def __call__(self, stream_id, **params):
        p = self.params.copy()
        p.update(params)

        for plugin in self.plugins:
            p = plugin.applyToParams(self.site, self.form, p)

        stream = self.site.createStream(stream_id, **p)

        for plugin in self.plugins:
            stream = plugin.applyToStream(self.site, self.form, stream)
        return stream


class StreamLoaderFactory:
    """Factory for StreamLoader class, accepts plugins as initialization
    parameters. Use it if you want to configure StreamLoader
    on static layer of your application.

    class Something:
        # unable to initialize StreamLoader, no site and form available here
        streamLoaderClass = StreamLoaderFactory(list_of_plugins)

        def foo(self):
            # site and form are only availbale here
            loader = self.streamLoaderClass(site, form)

    """
    
    def __init__(self, *args):
        self.plugins = args

    def __call__(self, site, form, **params):
        return StreamLoader(site, form, self.plugins, **params)


# compatibility object, use StreamLoaderFactory directly
PagedStreamLoader = StreamLoaderFactory(Page(), Order())


# vim: ts=8 sts=4 sw=4 ai et
