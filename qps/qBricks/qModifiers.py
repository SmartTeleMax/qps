# $Id: qModifiers.py,v 1.1 2005/03/16 13:45:46 corva Exp $

'''Brick modifiers classes'''

class StreamModifier(object):
    """Modifier interface,

    All modifiers have to define one of the following methods.

    modifyStream is called for a stream.

    modifyItem is called for item if feature was placed in itemModifiers by
    modifyStream.

    If you need only to modify a stream  - redefine modifyStream method,
    if you need to modify an item - redefine modifyItem"""
    
    def __call__(self, stream):
        stream.itemModifiers.append(self.modifyItem)
        self.modifyStream(stream)

    def modifyStream(self, stream):
        "Is called with stream instance as stream param"

    def modifyItem(self, item):
        "Is called with item instance as item param"


class ItemPathModifier(StreamModifier):
    """Modifies an item's path method.
    
    WARNING!  This modifier breaks consistency of path() and PathParser,
    so almost any site with it will be broken.  Use ItemPathModifier
    only if you know what you are doing.
    
    Usage:

    ItemPathModifier(pathTemplate)
    
    pathTemplate is string passed to qps.qUtils.interpolateString
    with namespace {'brick': item},

    Example:

    ItemPathModifier('%(brick.stream.path()' \
                     '%(brick.fields.id.convertToString(brick.id))s')

    this modifier instance generates the same path as
    qps.qBrick.qBase.Item.path()
    """
    
    def __init__(self, template):
        self.template = template
    
    def modifyItem(self, item):
        import new
        
        def path(self):
            import qps.qUtils
            path = qps.qUtils.interpolateString(self._path_template,
                                                {'brick': self})
            self.path = new.instancemethod(lambda self: path, item,
                                           item.__class__)
            return path
        
        item._path_template = self.template
        item.path = new.instancemethod(path, item, item.__class__)
