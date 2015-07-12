# -*- encoding: utf-8 -*-
from lxml import etree

from lxml.builder import ElementMaker
from pymarc import marcxml
from bpp.marc import to_marc

XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'

class OAIMARC(object):

    def __init__(self, prefix, config, db):
        self.prefix = prefix
        self.config = config
        self.db = db

        # self.ns = {'marc21slim': 'http://www.loc.gov/MARC21/slim',}

    def get_namespace(self):
        return self.ns[self.prefix]

    def get_schema_location(self):
        return self.schemas[self.prefix]

    def __call__(self, element, metadata):

        data = metadata.record

        # OAI_MARC =  ElementMaker(namespace=self.ns['oai_marc'], nsmap =self.ns)
        # DC = ElementMaker(namespace=self.ns['dc'])
        # 
        # oai_dc = OAI_DC.dc()
        # oai_dc.attrib['{%s}schemaLocation' % XSI_NS] = '%s %s' % (
        #     self.ns['oai_dc'],
        #     self.schemas['oai_dc'])
        # 
        # for field in ['title', 'creator', 'subject', 'description',
        #               'publisher', 'contributor', 'type', 'format',
        #               'identifier', 'source', 'language', 'date',
        #               'relation', 'coverage', 'rights']:
        #     el = getattr(DC, field)
        #     for value in data['metadata'].get(field, []):
        #         if field == 'identifier' and data['metadata'].get('url'):
        #             value = data['metadata']['url'][0]
        #         oai_dc.append(el(value))
        # 
        # element.append(oai_dc)

        orig = metadata.record['metadata'].orig
        marc = to_marc(orig)
        xml = marcxml.record_to_xml(marc)
        # TODO: niewydajne, marcxml zwraca string a tu ma byc etree
        element.append(etree.fromstring(xml))