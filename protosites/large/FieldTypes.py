from qps.qFieldTypes import *
import qps.qFieldTypes as FT

try:
    import stripogram
except ImportError:
    STRING_FILTERED = STRING
    TEXT_FILTERED = TEXT
else:
    # STRING_FILTERED and TEXT_FILTERED fields are possible
    # if stripogram module presents.
    
    class StripogramFilter(stripogram.HTML2SafeHTML):
        can_close   = ['li', 'p', 'dd', 'dt', 'option']
        CDATA_CONTENT_ELEMENTS = []

    def html2safehtml(string, valid_tags=[]):
        valid_tags = [t.lower() for t in valid_tags]
        parser = StripogramFilter(valid_tags)
        parser.feed(string)
        parser.close()
        parser.cleanup()
        return parser.result

    allowed_tags = []

    class STRING_FILTERED(STRING):
        allowed_tags = allowed_tags
    
        def convertFromForm(self, form, name, item=None):
            value = FT.STRING.convertFromForm(self, form, name, item)
            value = html2safehtml(value, self.allowed_tags)
            return value

    class TEXT_FILTERED(TEXT):
        allowed_tags = allowed_tags
    
        def convertFromForm(self, form, name, item=None):
            value = FT.STRING.convertFromForm(self, form, name, item)
            value = html2safehtml(value, self.allowed_tags)
            return value

class ORDER_NUM(INTEGER):
    default = 100
    max_value = 100
    permissions = []
    indexPermissions=[('wheel', 'rw')]
    title = u"Order"
