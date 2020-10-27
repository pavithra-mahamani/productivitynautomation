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
  
'''
class CouchbaseDocCodeSpider(scrapy.Spider):
    name = 'cb_doc_spider'

    def __init__(self, url, urldict, exclude):
        self.url = url
        self.urldict = urldict
        self.exclude = exclude


    def start_requests(self):
        urls = [self.url]
        self.urldomain = urlparse(self.url).netloc
        self.urlscheme = urlparse(self.url).scheme
        self.allowed_domains = [self.urldomain]
        logging.info("-->urlscheme={}, urldomain={}".format(self.urlscheme, self.urldomain))
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        title = ''.join(response.css('title ::text').getall())
        file_title = re.sub('[ |()!-:@#$]', '', title)
        for coderef in response.css('code'):
            #logging.info("title:{} code...{}".format(title,coderef))
            for langref in coderef.xpath('//*[@data-lang]'):
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
                if not next_visit in self.urldict:
                    self.urldict.append(next_visit)
                    if not os.path.exists(file_extn):
                        os.makedirs(file_extn)
                    out = open("{}/{}Code.{}".format(file_extn, file_title, file_extn), "a")
                    out.write(comment_line+"\n\n")
                    out.write(' '.join(langref.xpath('//code[@data-lang="{}"]/text()'.format(codelang)).getall()))
                    out.write("\n")
                    out.flush()
                    out.close()


        for href in response.css('a::attr(href)'):
            if (self.exclude not in str(href)) and ((not 'data=\''+self.urlscheme
                                                  +'://'+self.urldomain+'\'' in str(href)) and (
                    'data=\'http' in str(href) and self.urldomain in str(href)) or (
                    not 'data=\'http' in str(href) and not 'data=\'#' in str(href))):
                #logging.info("href={}".format(href))

                try:
                    yield response.follow(href, callback=self.parse)
                except Exception as e:
                    pass

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--url", dest="url", default="https://docs.couchbase.com",
                        help="starting url")
    parser.add_argument("-e", "--exclude", dest="exclude", default="",
                        help="excluded string in url")
    options = parser.parse_args()
    return options

def main():
    options = parse_arguments()
    urldict = []

    process = CrawlerProcess(get_project_settings())
    process.crawl(CouchbaseDocCodeSpider, options.url, urldict, options.exclude)
    process.start()

if __name__ == "__main__":
    main()