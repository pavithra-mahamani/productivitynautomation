import couchbase
import json
from couchbase.cluster import Cluster, ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.options import LockMode
import sys
from optparse import OptionParser
from jenkinshelper import connect_to_jenkins
import xml.sax
import logging
import re

logger = logging.getLogger("rerun_failed_jobs")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

cluster = Cluster('couchbase://172.23.121.84', ClusterOptions(PasswordAuthenticator("Administrator", "password")), lockmode=LockMode.WAIT)

def parse_arguments():
    parser = OptionParser()
    parser.add_option("-c", "--config", dest="configfile", default=".jenkinshelper.ini",
                        help="Configuration file")
    parser.add_option("-u", "--url", dest="build_url_to_check",
                      default='http://qa.sc.couchbase.com', help="Build URL to check")
    parser.add_option("-n", "--noop", dest="noop", help="Just print hanging jobs, don't stop them", action="store_true")
    
    parser.add_option("-a", "--aborted", dest="aborted", help="Aborted jobs", action="store_true")

    # TODO: Any way to get jenkins job number based on os, component, subcomponent
    # Would need to get all running jobs, go through parameters and retrieve if those params exist. If job exists then abort it before dispatching new job
    # parser.add_option("-s", "--stop", dest="stop", help="Stop a running job before starting this one", action="store_true")

    parser.add_option("-f", "--failed", dest="failed", help="Jobs with failed tests", action="store_true", default=True)

    parser.add_option("-p", "--previous-builds", dest="previous_builds", help="Which previous builds to check for failed jobs")

    parser.add_option("-b", "--build", dest="build", help="Build version e.g. 7.0.0-3594")

    parser.add_option("-d", "--dispatcher-jobs", dest="dispatcher_jobs", help="only rerun jobs managed by a dispatcher", action="store_true")

    parser.add_option("-o", "--os", dest="os", help="List of operating systems: win, magma, centos, ubuntu, mac, debian, suse, oel")
    parser.add_option("-y", "--components", dest="components", help="List of components")

    options, _ = parser.parse_args()

    if not options.build:
        logger.error("No --build given")
        sys.exit(1)

    if not options.previous_builds:
        logger.error("No --previous-builds given")
        sys.exit(1)

    if options.os:
        options.os = options.os.split(",")

    if options.components:
        options.components = options.components.split(",")
    
    if options.previous_builds:
        options.previous_builds = options.previous_builds.split(",")

    logger.info("Given build url={}".format(options.build_url_to_check))

    return options

if __name__ == "__main__":
    options = parse_arguments()
    server = connect_to_jenkins(options.build_url_to_check)

    query = "select component, subcomponent, failCount, url, build_id from server where `build` in {} and url like '{}/job/%'".format(options.previous_builds, options.build_url_to_check)

    if options.aborted:
        query += " and result = 'ABORTED'"

    if options.failed:
        query += " and failCount > 0"

    if options.os:
        query += " and lower(os) in {}".format(options.os)

    if options.components:
        query += " and lower(component) in {}".format(options.components)

    print(query)

    rows = cluster.query(query).rows()

    for row in rows:

        if options.components and not re.search(options.components, row['component'].lower()):
            continue
        
        job_name = row['url'].replace("{}/job/".format(options.build_url_to_check), "").strip("/")

        print("{}{} {} failures".format(row['url'], row['build_id'], row['failCount']))

        try:
            job = server.get_job_info(job_name)
            info = server.get_build_info(job_name, row['build_id'])

            parameters = [action['parameters'] for action in info['actions'] if 'parameters' in action][0]
            parameters = {param['name']: param['value'] for param in parameters}

            if 'dispatcher_params' not in parameters:

                if options.dispatcher_jobs:
                    continue

                # TODO: Needs special casing

            else:
                dispatcher_params = json.loads(parameters['dispatcher_params'][11:])

                if job_name != "test_suite_executor":
                    executor_suffix = job_name.replace("test_suite_executor-", "")

                if executor_suffix:
                    dispatcher_params['executor_suffix'] = executor_suffix

                dispatcher_params['fresh_run'] = False
                dispatcher_params['version_number'] = options.build
                dispatcher_params.pop("dispatcher_url") # invalid parameter

                build_url = server.build_job_url("test_suite_dispatcher", parameters=dispatcher_params)

                print("Build URL: {}\n".format(build_url))

                # if not options.noop:
                #     server.build_job("test_suite_dispatcher", parameters=dispatcher_params)

            
        except Exception as e:
            continue
