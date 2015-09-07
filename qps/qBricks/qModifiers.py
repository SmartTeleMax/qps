'''Brick modifiers classes'''

import qps.qUtils
import weakref

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
                     '%(brick.fields.id.convertToString(brick.id, brick))s')

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


class GroupsFeature(StreamModifier):
    """Feature for creating custom security groups, based
    on item's fields values.

    Interface:

    GroupsFeature(templates=TEMPLATES,
                  collectionTemplates=COLLECTION_TEMPLATES)

    TEMPLATES and COLLECTION_TEMPLATES are lists of tuples (name, template)
    where name is field name and template is a PySI interpolated template
    with namespace of one accessable object - 'value'

    How it works?

    TEMPLATES describes templates for non-iterable fields,
    if field (of given name) value is true group name is calculated with
    template. Example:

    TEMPLATE=[('status', 'have_status'), ('status', 'status-%(value.id)s')]

    if there is a 'status' field of FOREIGN_DROP type and it's true,
    two security group names are generated:
    'have_status' and 'status-12' (if foreign item has id=12)

    COLLECTION_TEMPLATES works the same as TEMPLATE, but field of given name
    is processed in iteration and template is used for every entry what is
    true. For example:

    COLLECTION_TEMPLATE=[('sections', 'section-%(value.id)s')]

    if sections field is [Item(id=politics), Item(id=sports), Item(id=society)]
    three group named are generated:

    ['section-politics', 'section-sports', 'section-society']"""


    class Groups:
        """Instance of this class becomes an Item.groups, at now groups
        are used only in two operations: __add__ and __iter__, both of them
        are declared, and in moment of call groups are actually calculated"""

        def __init__(self, item, defaultGroups, **kwargs):
            self.item = weakref.proxy(item)
            self.defaultGroups = defaultGroups[:]
            self.params = kwargs

        def groups(self):
            from qps.qUtils import interpolateString as render
            item = self.item
            groups = self.defaultGroups
            for name, template in self.params.get('templates', []):
                value = getattr(item, name)
                if type(template) in (list, tuple):
                    templateTrue, templateFalse = template
                else:
                    templateTrue, templateFalse = (template, None)
                if value and templateTrue:
                    groups.append(
                        render(templateTrue, {'name': name, 'value': value}))
                elif templateFalse:
                    groups.append(
                        render(templateFalse, {'name': name, 'value': value}))

            for name, template in self.params.get('collectionTemplates', []):
                for value in getattr(item, name):
                    if value:
                        groups.append(
                            render(template, {'name': name, 'value': value}))

            return groups
        groups = qps.qUtils.CachedAttribute(groups)

        def __add__(self, other):
            return self.groups+other

        def __iter__(self):
            return iter(self.groups)


    def __init__(self, **kwargs):
        self.params = kwargs

    def modifyItem(self, item):
        item.groups = self.Groups(item, item.groups, **self.params)


class Permissions:
    """Instance of this class becomes an Item.groups, at now groups
    are used only in two operations: __add__ and __iter__, both of them
    are declared, and in moment of call groups are actually calculated"""

    def __init__(self, item, defaultPermissions, **kwargs):
        self.item = weakref.proxy(item)
        self.defaultPermissions = defaultPermissions[:]
        self.params = kwargs

    def permissions(self):
        from qps.qUtils import interpolateString as render
        item = self.item
        permissions = dict(self.defaultPermissions)
        for name, template in self.params.get('templates', []):
            value = getattr(item, name)
            if value:
                group, perm = template
                group = render(group, {'name': name, 'value': value})
                permissions[group] = perm

        for name, template in self.params.get('collectionTemplates', []):
            for value in getattr(item, name):
                if value:
                    group, perm = template
                    group = render(group, {'name': name, 'value': value})
                    permissions[group] = perm

        return permissions.items()
    permissions = qps.qUtils.CachedAttribute(permissions)

    def __iter__(self):
            return iter(self.permissions)


class ItemPermissionsFeature(StreamModifier):
    def __init__(self, **kwargs):
        self.params = kwargs

    def modifyItem(self, item):
        item.permissions = Permissions(item, item.permissions,
                                       **self.params)


class StreamPermissionsFeature(StreamModifier):
    def __init__(self, name, **kwargs):
        self.objectName = name # name of fields holder
        self.params = kwargs

    def __call__(self, stream):
        self.modifyStream(stream)

    def modifyStream(self, stream):
        stream.permissions = Permissions(getattr(stream, self.objectName),
                                         stream.permissions,
                                         **self.params)
