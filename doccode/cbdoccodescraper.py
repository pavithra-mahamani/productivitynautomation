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
  -p USEPATHFILE, --isusepathfile USEPATHFILE
                        is use path as file name
  
'''
class CouchbaseDocCodeSpider(scrapy.Spider):
    name = 'cb_doc_spider'

    def __init__(self, options):
        self.url = options.url
        self.exclude = options.exclude
        self.language = options.language
        self.cslanguage = options.cslanguage
        self.isusepathfile = options.isusepathfile
        self.isperpagedir = options.isperpagedir
        self.iscrawl = options.iscrawl

    def start_requests(self):
        urls = [self.url]
        self.urldomain = urlparse(self.url).netloc
        self.urlscheme = urlparse(self.url).scheme
        allowed_domains = [self.urldomain]
        logging.info("-->urlscheme={}, urldomain={}".format(self.urlscheme, self.urldomain))
        for url in urls:
            if not ".htm" in url and not url.endswith("/") and not url.endswith(self.urldomain):
                yield scrapy.Request(url=url, callback=self.save_nontext)
            else:
                yield scrapy.Request(url=url, callback=self.parse)

    def save_nontext(self, response):
        logging.info("--> Downloading non text file...{}".format(response.url))
        file_name = os.path.basename(urlparse(response.url).path)
        dirpath = "downloads/"+re.sub('\W', '', urlparse(response.url).path.split(file_name)[0])
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)
        path = dirpath + "/" + file_name
        with open(path, "wb") as f:
            f.write(response.body)

    def parse(self, response):
        try:
            if not ".htm" in response.url and not response.url.endswith("/") and not \
                    response.url.endswith(
                    self.urldomain):
                yield scrapy.Request(response.url, callback=self.save_nontext)
                return
            else:
                title = ''.join(response.css('title ::text').getall())
        except scrapy.exceptions.NotSupported as nse:
            logging.warning("--> Not supported url file ...{}".format(response.url))
            with open("not_supported.txt", "w") as f:
                f.write(response.url)
            return

        file_title = re.sub('\W', '', title)

        LANG_SELECTOR = '//*[@data-lang]'
        if self.cslanguage:
            LANG_SELECTOR = '//*[@data-lang="{}"]'.format(self.cslanguage)
        #for coderef in response.css('code'):
        #logging.info("title:{} code...{}".format(title,response))
        lang_dict = []
        for langref in response.xpath(LANG_SELECTOR):
                #logging.info("code snippet...{}".format(langref))
                codelang = langref.attrib['data-lang']
                codelang_lower = codelang.lower()

                if not codelang_lower in lang_dict:
                    lang_dict.append(codelang_lower)
                else:
                    continue

                comment_text = "Automated code extraction on {} from URL: {}".format(
                    datetime.datetime.now(), response.url)
                comment_symbol = "// "
                comment_line = comment_symbol + comment_text
                if codelang_lower == "java":
                    file_extn = 'java'
                elif codelang_lower == "python":
                    file_extn = 'py'
                    comment_symbol = "# "
                    comment_line = comment_symbol + comment_text
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
                    comment_symbol = "# "
                    comment_line = comment_symbol + comment_text
                else:
                    file_extn = codelang.lower()

                if (codelang_lower == "bash") or (codelang_lower == "console"):
                    comment_symbol = "# "
                    comment_line = comment_symbol + comment_text

                next_visit = response.url

                def write_code():
                    if self.isusepathfile:
                        file_urlpath = re.sub('\W', '',
                                              urlparse(response.url).path.split("htm")[0])
                    else:
                        file_urlpath = ''

                    if self.isperpagedir:
                        out_dir = "{}/{}".format(file_title, file_urlpath, file_extn)
                        out_file = "{}/{}Code.{}".format(out_dir, file_urlpath, file_extn)
                    else:
                        out_dir = file_extn
                        out_file = "{}/{}_{}Code.{}".format(out_dir, file_title, file_urlpath,
                                                        file_extn)
                    if not os.path.exists(out_dir):
                        os.makedirs(out_dir)

                    out = open(out_file, "a")
                    out.write(comment_line + "\n\n")
                    snippet_comment = '\n\n{}Next snippet \n'.format(comment_symbol)
                    out.write(snippet_comment.join(
                        langref.xpath('//code[@data-lang="{}"]/text()'.format(codelang)).getall()))
                    out.write("\n")
                    out.flush()
                    out.close()

                if self.language:
                    if re.search(self.language, codelang_lower):
                        write_code()
                else:
                    write_code()

        if self.iscrawl:
            for href in response.css('a::attr(href)'):
                url_referer = str(response.request.headers.get('Referer', self.urldomain))
                if not self.exclude:
                    if self.urldomain in url_referer and (( 'data=\'' +
                            self.urlscheme + '://' +
                         self.urldomain + '\'' in str(href)) and ('data=\'http' in str(
                        href) and self.urldomain in str(href)) or (not 'data=\'http' in str(
                        href) and not 'data=\'ftp' in str(
                        href) and not 'data=\'#' in str(href))):
                        #logging.info("Matched url in data:{}, {}".format(
                        #    response.request.headers.get('Referer', None), href.get()))
                        try:
                            #if not ".htm" in href.get() and not href.get().endswith(
                            #        "/") and not href.get().endswith(self.urldomain):
                            if href.get().endswith(".zip"):
                                logging.info("--> zip file...{}".format(href.get()))
                                yield response.follow(href, callback=self.save_nontext)
                            else:
                                yield response.follow(href, callback=self.parse)
                        except Exception as e:
                            pass
                    else:
                        #logging.info("Not matched url in data:{}".format(href))
                        pass
                elif self.urldomain in url_referer and ( not re.search(self.exclude,str(href))) and (\
                        ('data=\'' +
                            self.urlscheme + '://' +
                         self.urldomain + '\'' in str(href)) and ('data=\'http' in str(
                        href) and self.urldomain in str(href)) or (not 'data=\'http' in str(
                        href) and not 'data=\'#' in str(href))):
                    try:
                        #if not ".htm" in href.get() and not href.get().endswith(
                        #        "/") and not href.get().endswith(self.urldomain):
                        if href.get().endswith(".zip"):
                            logging.info("--> zip file...{}".format(href.get()))
                            yield response.follow(href, callback=self.save_nontext)
                        else:
                            yield response.follow(href, callback=self.parse)
                    except Exception as e:
                        pass
        else:
            logging.warning("--> No crawl!")

def str2bool(v):
    if isinstance(v, bool):
       return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--url", dest="url", default="https://docs.couchbase.com",
                        help="[https://docs.couchbase.com] starting url")
    parser.add_argument("-e", "--exclude", dest="exclude",
                        help="excluded regular expression string in url. Ex: -e '2.0|2.5|2.6'")
    parser.add_argument("-l", "--language", dest="language", help="extract specific language(s) "
                                             "regular expression. Ex: -l 'java|python|go|^c$' ")
    parser.add_argument("-csl", "--cslanguage", dest="cslanguage", help="extract specific "
                                                        "case sensitive language. Ex: -csl Java")
    parser.add_argument("-p", "--isusepathfile", default=True, dest="isusepathfile", type=str2bool, nargs='?',
                        const=True, help="[True] is use path as file name")
    parser.add_argument("-g", "--isperpagedir", default=True, dest="isperpagedir", type=str2bool, nargs='?',
                        const=True, help="[True] is per page output directory required")
    parser.add_argument("-c", "--iscrawl", default=True, dest="iscrawl", type=str2bool, nargs='?',
                        const=True, help="[True] is crawl")
    options = parser.parse_args()
    return options

def main():
    options = parse_arguments()
    process = CrawlerProcess(get_project_settings())
    process.crawl(CouchbaseDocCodeSpider, options)
    process.start()

if __name__ == "__main__":
    main()