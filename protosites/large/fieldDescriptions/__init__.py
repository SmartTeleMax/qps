from qps.qUtils import DictImporter
import FieldTypes as FT

itemIDFields = {}
itemFieldsOrder = DictImporter("fieldDescriptions", name="itemFieldsOrder")
itemFields = DictImporter("fieldDescriptions", name="itemFields")
itemExtFields = DictImporter("fieldDescriptions", name="itemExtFields")
