# $Id: qSQL.py,v 1.14 2005/01/19 23:46:53 corva Exp $

'''Classes for bricks with data stored in XML file'''

import logging
logger = logging.getLogger(__name__)
from xml.sax import saxutils, make_parser

import qBase, qStatic
from qps import qUtils


class XMLHandler(saxutils.DefaultHandler):
    """Handles xml with following structure:

    <items>
        <item>
            <id>1</id>
            <field1></field1>
        </item>
        <item>
            <id>1</id>
            <field1></field1>
        </item>
    </items>"""
    
    def __init__(self, stream):
        self.stream = stream
        self.field_names = stream.fields.main.keys()
        self.clearBuffer()

    def clearBuffer(self):
        self.buffer = []

    def getBuffer(self):
        return ''.join(self.buffer)

    def characters(self, chunk):
        self.buffer.append(chunk)
   
    def startElement(self, name, attrs):
        if name == 'item':
            self.fieldDict = {}
        elif name in self.field_names:
            self.clearBuffer()
            
    def endElement(self, name):
        if name == 'item':
            id = self.stream.fields.id.convertFromString(
                self.fieldDict[self.stream.fields.idFieldName], self.stream)
            item = self.stream.createNewItem(id)

            for name, value in self.fieldDict.items():
                field_type = self.stream.fields[name]
                setattr(item, name, field_type.convertFromString(value))
            
            self.stream.itemList.append(item)
        elif name in self.field_names:
            self.fieldDict[name] = self.getBuffer()

        
class XMLStream(qBase.Stream):
    itemClass = qStatic.StaticItem
    filename = None # file name of source file
    handlerClass = XMLHandler # xml handler

    def getSource(self):
        """Returns a xml source (file object, file name, or anything
        compatible with parser, returned by xml.sax.make_parser()"""
        return qUtils.interpolateString(self.filename, {'site': self.site})

    def retrieve(self, ignoreStatus=0):
        if not self._retrieved or ignoreStatus:
            handler = self.handlerClass(self)
            parser = make_parser()
            parser.setContentHandler(handler)
            parser.parse(self.getSource())
            self._retrieved = 1
        
    def retrieveItem(self, item_id):
        self.retrieve()
        return self.getItem(item_id)

    def deleteItems(self, item_ids):
        pass

    def clear(self):
        pass

    def countItems(self, ignoreStatus=0):
        return len(self)
