import re
import datetime
from urllib.parse import urlparse
import os
import sys
import argparse

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import Rule
import logging
from scrapy.utils.project import get_project_settings

'''
  Description: Automatic documentation code scraper for the code testing.
  Usage: python3 cbdoccodescraper.py [--url https://docs.couchbase.com]
  
  I/O:-
  Web page having the below code snippet:
  
  <code ... data-lang="<lang>" ..>
     actual code
  </code>
  
  Extracted as
   <lang>/<pagetitle>Code.<lang>
   
   python3 cbdoccodescraper.py --help
usage: cbdoccodescraper.py [-h] [-u URL] [-e EXCLUDE] [-l LANGUAGE] [-csl CSLANGUAGE] [-p USEPATHFILE]

optional arguments:
  -h, --help            show this help message and exit
  -u URL, --url URL     starting url
  -e EXCLUDE, --exclude EXCLUDE
                        excluded string in url
  -l LANGUAGE, --language LANGUAGE
                        extract specific language
  -csl CSLANGUAGE, --cslanguage CSLANGUAGE
                        extract specific case sensitive language
  -p USEPATHFILE, --usepathfile USEPATHFILE
                        use path as file name
  
'''
class CouchbaseDocCodeSpider(scrapy.Spider):
    name = 'cb_doc_spider'

    def __init__(self, urldict, options):
        self.urldict = urldict
        self.url = options.url
        self.exclude = options.exclude
        self.language = options.language
        self.cslanguage = options.cslanguage
        self.usepathfile = options.usepathfile

    def start_requests(self):
        urls = [self.url]
        self.urldomain = urlparse(self.url).netloc
        self.urlscheme = urlparse(self.url).scheme
        allowed_domains = [self.urldomain]
        logging.info("-->urlscheme={}, urldomain={}".format(self.urlscheme, self.urldomain))
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        title = ''.join(response.css('title ::text').getall())
        file_title = re.sub('[ |()!-:/@#$]', '', title)

        LANG_SELECTOR = '//*[@data-lang]'
        if self.cslanguage:
            LANG_SELECTOR = '//*[@data-lang="{}"]'.format(self.cslanguage)
        for coderef in response.css('code'):
            #logging.info("title:{} code...{}".format(title,coderef))
            for langref in coderef.xpath(LANG_SELECTOR):
                codelang = langref.attrib['data-lang']
                codelang_lower = codelang.lower()
                comment_text = "Automated code extraction on {} from URL: {}".format(
                    datetime.datetime.now(), response.url)
                comment_line = "// "+comment_text
                if codelang_lower == "java":
                    file_extn = 'java'
                elif codelang_lower == "python":
                    file_extn = 'py'
                    comment_line = "# "+comment_text
                elif codelang_lower == "c++":
                    file_extn = 'cpp'
                elif codelang_lower == "javascript":
                    file_extn = 'js'
                elif codelang_lower == "golang":
                    file_extn = 'go'
                elif codelang_lower ==  "c#" or codelang_lower == "csharp":
                    file_extn = 'cs'
                elif codelang_lower == "bourne" or codelang_lower == 'shell':
                    file_extn = 'sh'
                    comment_line = "# " + comment_text
                else:
                    file_extn = codelang.lower()

                if (codelang_lower == "bash") or (codelang_lower == "console"):
                    comment_line = "# " + comment_text

                next_visit = response.url

                def write_code():
                    if not os.path.exists(file_extn):
                        os.makedirs(file_extn)
                    if self.usepathfile:
                        file_urlpath = re.sub('[ |()!-:/@#$]', '', urlparse(
                            response.url).path.split("htm")[0])
                    else:
                        file_urlpath = ''

                    out = open("{}/{}_{}Code.{}".format(file_extn, file_title, file_urlpath,
                                                       file_extn), "a")
                    out.write(comment_line + "\n\n")
                    out.write(' '.join(
                        langref.xpath('//code[@data-lang="{}"]/text()'.format(codelang)).getall()))
                    out.write("\n")
                    out.flush()
                    out.close()

                if not next_visit in self.urldict:
                    self.urldict.append(next_visit)
                    if self.language:
                        if re.search(self.language, codelang_lower):
                            write_code()
                    else:
                        write_code()

        for href in response.css('a::attr(href)'):
            url_referer = str(response.request.headers.get('Referer', self.urldomain))
            if not self.exclude:
                if self.urldomain in url_referer and (( 'data=\'' +
                        self.urlscheme + '://' +
                     self.urldomain + '\'' in str(href)) and ('data=\'http' in str(
                    href) and self.urldomain in str(href)) or (not 'data=\'http' in str(
                    href) and not 'data=\'#' in str(href))):
                    logging.info("Matched url in data:{}, {}".format(
                        response.request.headers.get('Referer', None), href))
                    try:
                        yield response.follow(href, callback=self.parse)
                    except Exception as e:
                        pass
                else:
                    logging.info("Not matched url in data:{}".format(href))
            elif self.urldomain in url_referer and ( not re.search(self.exclude,str(href))) and (\
                    ('data=\'' +
                        self.urlscheme + '://' +
                     self.urldomain + '\'' in str(href)) and ('data=\'http' in str(
                    href) and self.urldomain in str(href)) or (not 'data=\'http' in str(
                    href) and not 'data=\'#' in str(href))):
                try:
                    yield response.follow(href, callback=self.parse)
                except Exception as e:
                    pass

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--url", dest="url", default="https://docs.couchbase.com",
                        help="starting url")
    parser.add_argument("-e", "--exclude", dest="exclude",
                        help="excluded regular expression string in url")
    parser.add_argument("-l", "--language", dest="language", help="extract specific language(s) "
                                                                  "regular expression")
    parser.add_argument("-csl", "--cslanguage", dest="cslanguage", help="extract specific "
                                                                        "case sensitive language")
    parser.add_argument("-p", "--usepathfile", dest="usepathfile", help="use path as file "
                                                                             "name")
    options = parser.parse_args()
    return options

def main():
    options = parse_arguments()
    urldict = []

    process = CrawlerProcess(get_project_settings())
    process.crawl(CouchbaseDocCodeSpider, urldict, options)
    process.start()

if __name__ == "__main__":
    main()