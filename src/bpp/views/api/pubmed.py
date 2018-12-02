# -*- encoding: utf-8 -*-

import requests
from django.http import JsonResponse
from django.http.response import HttpResponseServerError
from django.views.generic.base import View

from lxml import etree

# multiple: http://www.ncbi.nlm.nih.gov/pubmed/?term=test+&report=xml&format=text
# single:   http://www.ncbi.nlm.nih.gov/pubmed/?term=Appliasdofijasodfijaosidjfoasdifjcation+&report=xml&format=text
# brak:     http://www.ncbi.nlm.nih.gov/pubmed/?term=Appliasdofijasodfijaosidjfoasdifjcation+&report=xml&format=text


#@ BLOKUJE
def get_data_from_ncbi(title, url="http://www.ncbi.nlm.nih.gov/pubmed/"):
    res = requests.get(url=url, params={
        'term': title,
        'report': 'xml',
        'format': 'xml'
    })

    if res.status_code == 200:
        try:
            text = res.text.split("<pre>", 1)[1].strip()
        except IndexError:
            return []
        text = text.split("</pre>", 1)[0].strip()
        text = text.replace("&lt;", "<").replace("&gt;", ">")
        text = "<root>" + text + "</root>"
        xml = etree.fromstring(text)
        return xml.getchildren()


def parse_data_from_ncbi(elem):
    ret = {}

    pmid = elem.xpath("//PubmedData/ArticleIdList/ArticleId[@IdType='pubmed']/text()")
    if pmid and len(pmid) == 1:
        ret['pubmed_id'] = pmid[0]

    doi = elem.xpath("//PubmedData/ArticleIdList/ArticleId[@IdType='doi']/text()")
    if doi and len(doi) == 1:
        ret['doi'] = doi[0]

    ret['has_abstract_text'] = 'false'
    abstract_text = elem.xpath("//MedlineCitation/Article/Abstract/AbstractText/text()")
    if abstract_text and len(abstract_text) == 1:
        ret['has_abstract_text'] = 'true'

    return ret

class PubmedConnectionFailure(HttpResponseServerError):
    pass


class GetPubmedIDView(View):
    def post(self, request, *args, **kw):
        tytul = request.POST.get('t', '').strip()

        if tytul:
            data = get_data_from_ncbi(title=tytul)
            if data is None:
                return PubmedConnectionFailure()

            if len(data) == 1:
                return JsonResponse(parse_data_from_ncbi(data[0]))

        return JsonResponse({})
