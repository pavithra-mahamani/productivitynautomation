from typing import Dict, List, Optional
import jenkinshelper
from time import time as current_time
import traceback
from datetime import datetime
from pytz import timezone
import requests
from optparse import OptionParser
import logging
import re
import csv
import os

logger = logging.getLogger("hanging_jobs")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

def parameters_for_job(server, name, number):
    info = server.get_build_info(name, number)
    parameters = {}
    for a in info["actions"]:
        try:
            if a["_class"] == "hudson.model.ParametersAction":
                for param in a["parameters"]:
                    if "name" in param and "value" in param:
                        parameters[param['name']] = param['value']
        except KeyError:
            pass
    start_time = datetime.fromtimestamp(int(info['timestamp']) / 1000, tz=timezone("US/Pacific"))
    return parameters, start_time

def passes_component_filter(parameters, options):

    # non executor jobs (no component/subcomponent) pass the filter
    if "component" not in parameters or "subcomponent" not in parameters:
        return True

    component = parameters['component']
    subcomponent = parameters['subcomponent']

    if options.include_components:

        if component not in options.include_components:
            return False

        included_subcomponents = options.include_components[component]
        
        # NOTE:
        # if included_subcomponents is None, all subcomponents are included
        # if included_subcomponents is empty array, no subcomponents are includes
        if included_subcomponents is not None and subcomponent not in included_subcomponents:
            return False

    if options.exclude_components and component in options.include_components:
        excluded_subcomponents = options.include_components[component]

        if excluded_subcomponents is None or subcomponent in excluded_subcomponents:
            return False

    return True


def get_hanging_jobs(server, options):
    running_builds = server.get_running_builds()

    hanging_jobs = []

    for build in running_builds:
        if options.include and not re.search(options.include, build['name']):
            continue

        if options.exclude and re.search(options.exclude, build['name']):
            continue

        parameters, start_time = parameters_for_job(server, build['name'], build['number'])

        if not passes_component_filter(parameters, options):
            continue

        try:
            latest_timestamp = None
            start_download_time = current_time()
            download_complete = True
            console = []
            for line in requests.get(build['url'] + 'consoleText', stream=True).iter_lines():
                console.append(line)
                if current_time() > start_download_time + options.download_timeout:
                    download_complete = False
                    break
            if not download_complete:
                logger.error("{} skipped (downloading console log took too long)".format(build['url']))
                continue

            for line in reversed(console):

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
                    break
                except Exception:
                    pass

                try:
                    split = line.split(" ")
                    day = split[0].split("[")[1]
                    time = split[1].split("]")[0].split(",")[0]
                    latest_timestamp = parse_timestamp(day + " " + time, "%Y-%m-%d %H:%M:%S")
                    break
                except Exception:
                    pass

                try:
                    # [2020-10-28T23:36:38-07:00, sequoiatools/cmd:825833] 300

                    timestamp = line.split(" ")[0].split("[")[1][:19]
                    latest_timestamp = parse_timestamp(timestamp, "%Y-%m-%dT%H:%M:%S")
                    break
                except Exception:
                    pass

            if latest_timestamp or (options.force and re.search(options.force, build['name'])):
                
                now = datetime.now().astimezone()
                forced = False

                if not latest_timestamp:
                    latest_timestamp = start_time
                    forced = True

                difference = (now - latest_timestamp).total_seconds() / 60

                if difference >= options.timeout:
                    logger.info("{} is hanging (last console output: {} ({:2.2f} minutes ago)".format(build['url'], latest_timestamp, difference))

                    build['version_number'] = parameters['version_number'] if "version_number" in parameters else ""
                    build['component'] = parameters['component'] if "component" in parameters else ""
                    build['subcomponent'] = parameters['subcomponent'] if "subcomponent" in parameters else ""

                    build['last_console_output'] = round(difference)
                    build['forced'] = forced
                    hanging_jobs.append(build)

            else:

                logger.warning("timestamp not found for {}".format(build['url']))
            
        except Exception:
            traceback.print_exc()
            pass

    return hanging_jobs

def write_to_csv(jobs, options):
    if options.output:
        output_path = os.path.join(options.output, "hung_jobs.csv")
    else:
        output_path = "hung_jobs.csv"
    with open(output_path, 'w') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_rows = [['version_number', 'component', 'subcomponent', 'job', 'last_console_output_minutes', 'forced']]
        for job in jobs:
            csv_rows.append([job['version_number'], job['component'], job['subcomponent'], job['url'], job['last_console_output'], job['forced']])
        csv_writer.writerows(csv_rows)

def parse_components(components_str: str):
    component_map: Dict[str, Optional[List[str]]] = {}
    components: List[str] = components_str.split(" ")
    for component in components:
        if ":" in component:
            [component_name, subcomponents] = component.split(":")
            component_map[component_name] = subcomponents.split(",")
        else:
            component_map[component] = None
    return component_map


def parse_arguments():
    parser = OptionParser()
    parser.add_option("-c", "--config", dest="configfile", default=".jenkinshelper.ini",
                        help="Configuration file")
    parser.add_option("-u", "--url", dest="build_url_to_check",
                      default='http://qa.sc.couchbase.com', help="Build URL to check")
    parser.add_option("-t", "--timeout", dest="timeout", help="No console output timeout (minutes)", default=60, type="int")
    parser.add_option("-e", "--exclude", dest="exclude", help="Regular expression of job names to exclude")
    parser.add_option("-i", "--include", dest="include", help="Regular expression of job names to include")
    parser.add_option("-n", "--noop", dest="print", help="Just print hanging jobs, don't stop them", action="store_true")
    parser.add_option("-o", "--output", dest="output", help="Directory to output the CSV to")
    parser.add_option("--include_components", dest="include_components", help="List of component and subcomponents to include in format component1:subcomponent1,subcomponent2 component2:subcomponent3 component3")
    parser.add_option("--exclude_components", dest="exclude_components", help="List of components and subcomponents to exclude in format component1:subcomponent1,subcomponent2 component2:subcomponent3 component3")
    parser.add_option("-f", "--force", dest="force", help="Regular expression of job names to abort if no timestamp found and running time > timeout")
    parser.add_option("--download_timeout", dest="download_timeout", help="Timeout for downloading job log in secs", type="int", default="10")

    options, args = parser.parse_args()

    if len(args) == 1:
        options.build_url_to_check = args[0]

    if options.include_components:
        options.include_components = parse_components(options.include_components)

    if options.exclude_components:
        options.exclude_components = parse_components(options.exclude_components)

    logger.info("Given build url={}".format(options.build_url_to_check))

    return options

def stop_hanging_jobs(server, hanging_jobs):
    for job in hanging_jobs:
        logger.info("Stopping {}/{}".format(job['name'], job['number']))
        server.stop_build(job['name'], job['number'])
    

if __name__ == "__main__":
    options = parse_arguments()
    server = jenkinshelper.connect_to_jenkins(options.build_url_to_check)
    hanging_jobs = get_hanging_jobs(server, options)
    if len(hanging_jobs) > 0:
        write_to_csv(hanging_jobs, options)
        if not options.print:
            stop_hanging_jobs(server, hanging_jobs)