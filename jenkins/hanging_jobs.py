import jenkinshelper
import traceback
from datetime import datetime
import pytz
from pytz import timezone
import requests
from optparse import OptionParser
import logging
import re

logger = logging.getLogger("hanging_jobs")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

def get_hanging_jobs(server, timeout):
    running_builds = server.get_running_builds()

    hanging_jobs = []

    for build in running_builds:
        try:
            latest_timestamp = None
            console = requests.get(
                build['url'] + 'consoleText').iter_lines(decode_unicode=True)
            for line in console:

                def parse_timestamp(timestamp, format):
                    timestamp = datetime.strptime(timestamp, format)
                    timestamp = timezone("US/Pacific").localize(timestamp).astimezone()
                    return timestamp

                try:
                    # new_install.py format
                    split = line.split(" ")
                    day = split[0]
                    time = split[1].split(",")[0]
                    latest_timestamp = parse_timestamp(day + " " + time, "%Y-%m-%d %H:%M:%S")
                    continue
                except Exception:
                    pass

                try:
                    split = line.split(" ")
                    day = split[0].split("[")[1]
                    time = split[1].split("]")[0].split(",")[0]
                    latest_timestamp = parse_timestamp(day + " " + time, "%Y-%m-%d %H:%M:%S")
                    continue
                except Exception:
                    pass

                try:
                    # [2020-10-28T23:36:38-07:00, sequoiatools/cmd:825833] 300

                    timestamp = line.split(" ")[0].split("[")[1][:19]
                    latest_timestamp = parse_timestamp(timestamp, "%Y-%m-%dT%H:%M:%S")
                    continue
                except Exception:
                    pass

            if latest_timestamp:
                
                now = datetime.now().astimezone()
                difference = (now - latest_timestamp).total_seconds() / 60

                if difference >= timeout:
                    logger.info("{} is hanging (last console output: {} ({:2.2f} minutes ago)".format(build['url'], latest_timestamp, difference))
                    hanging_jobs.append(build)

            else:

                logger.warning("timestamp not found for {}".format(build['url']))
            
        except Exception as e:
            traceback.print_exc()
            pass

    return hanging_jobs

def parse_arguments():
    parser = OptionParser()
    parser.add_option("-c", "--config", dest="configfile", default=".jenkinshelper.ini",
                        help="Configuration file")
    parser.add_option("-u", "--url", dest="build_url_to_check",
                      default='http://qa.sc.couchbase.com', help="Build URL to check")
    parser.add_option("-t", "--timeout", dest="timeout", help="No console output timeout (minutes)", default=60, type="int")
    parser.add_option("-e", "--exclude", dest="exclude", help="Regular expression of job names to exclude")
    parser.add_option("-i", "--include", dest="include", help="Regular expression of job names to include")
    parser.add_option("-p", "--print", dest="print", help="Just print hanging jobs, don't stop them", action="store_true")

    options, args = parser.parse_args()


    if options.build_url_to_check:
        build_url_to_check = options.build_url_to_check

    if len(args)==1:
        build_url_to_check = args[0]

    if not build_url_to_check:
        logger.error("No jenkins build url given!")
        sys.exit(1)

    logger.info("Given build url={}".format(build_url_to_check))

    return options

def stop_hanging_jobs(server, hanging_jobs, include, exclude):
    for job in hanging_jobs:
        if options.include and not re.search(options.include, job['name']):
            logger.info("Skipping {}, not included".format(job['name']))
            continue

        if options.exclude and re.search(options.exclude, job['name']):
            logger.info("Skipping {}, excluded".format(job['name']))
            continue
        
        logger.info("Stopping {}/{}".format(job['name'], job['number']))
        # server.stop_build(job['name'], job['number'])
    

if __name__ == "__main__":
    options = parse_arguments()
    server = jenkinshelper.connect_to_jenkins(options.build_url_to_check)
    hanging_jobs = get_hanging_jobs(server, options.timeout)
    if not options.print:
        stop_hanging_jobs(server, hanging_jobs, options.include, options.exclude)