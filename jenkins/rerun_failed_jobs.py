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
import traceback
from deepdiff import DeepDiff
import requests
import jenkins
import time

logger = logging.getLogger("rerun_failed_jobs")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)


def parse_arguments():
    parser = OptionParser()
    parser.add_option("-c", "--config", dest="configfile", default=".jenkinshelper.ini",
                      help="Configuration file")
    parser.add_option("-u", "--url", dest="build_url_to_check",
                      default='http://qa.sc.couchbase.com', help="Build URL to check")
    parser.add_option("-n", "--noop", dest="noop",
                      help="Just print hanging jobs, don't stop them", action="store_true")

    parser.add_option("-a", "--aborted", dest="aborted",
                      help="Aborted jobs", action="store_true")

    parser.add_option("-s", "--stop", dest="stop",
                      help="Stop a running job before starting this one", action="store_true")

    parser.add_option("-f", "--failed", dest="failed",
                      help="Jobs with failed tests", action="store_true", default=True)

    parser.add_option("-p", "--previous-builds", dest="previous_builds",
                      help="Which previous builds to check for failed jobs")

    parser.add_option("-b", "--build", dest="build",
                      help="Build version e.g. 7.0.0-3594")

    parser.add_option("--server", dest="server",
                      help="Couchbase server host", default="172.23.121.84")
    parser.add_option("--username", dest="username",
                      help="Couchbase server username", default="Administrator")
    parser.add_option("--password", dest="password",
                      help="Couchbase server password", default="password")

    parser.add_option("-d", "--dispatcher-jobs", dest="dispatcher_jobs",
                      help="only rerun jobs managed by a dispatcher", action="store_true")

    parser.add_option("-o", "--os", dest="os",
                      help="List of operating systems: win, magma, centos, ubuntu, mac, debian, suse, oel")
    parser.add_option("--components", dest="components",
                      help="List of components to include")
    parser.add_option("--subcomponents", dest="subcomponents",
                      help="List of subcomponents to include")

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

    if options.subcomponents:
        if len(options.components) > 1:
            logger.error("Can't supply multiple components with subcomponents")
            sys.exit(1)
        options.subcomponents = options.subcomponents.split(",")

    if options.previous_builds:
        options.previous_builds = options.previous_builds.split(",")

    logger.info("Given build url={}".format(options.build_url_to_check))

    return options


def parameters_for_job(name, number, version_number=None):
    try:
        info = server.get_build_info(name, number)
    except jenkins.JenkinsException:
        if version_number:
            info = requests.get("http://cb-logs-qe.s3-website-us-west-2.amazonaws.com/{}/jenkins_logs/{}/{}/jobinfo.json".format(version_number, name, number)).json()
        else:
            raise ValueError("no version number for build missing from jenkins")
    parameters = {}
    for a in info["actions"]:
        try:
            if a["_class"] == "hudson.model.ParametersAction":
                for param in a["parameters"]:
                    if "name" in param and "value" in param:
                        parameters[param['name']] = param['value']
        except KeyError:
            pass
    return parameters


 # these parameters could be different even for duplicate jobs
ignore_params_list = ["descriptor", "servers", "dispatcher_params", "fresh_run", "rerun_params",
                          "retries", "timeout", "mailing_list", "addPoolServers", "version_number"]


def get_running_builds(server):
    # get all running builds so we know if a duplicate job is already running
    running_builds = server.get_running_builds()

    # server.get_running_builds() can take a while so these can be used to cache the value and reuse

    # with open("running_builds.json", 'w') as outfile:
    #     json.dump(running_builds, outfile)

    # with open("running_builds.json") as json_file:
    #     running_builds = json.load(json_file)

    builds_with_params = []

    for build in running_builds:
        parameters = parameters_for_job(build['name'], build['number'])
        for param in ignore_params_list:
            if param in parameters:
                parameters.pop(param)
        builds_with_params.append({
            "name": build['name'],
            "number": build['number'],
            "parameters": parameters
        })

    return builds_with_params

def get_duplicate_jobs(running_builds, job_name, parameters):
    parameters = parameters.copy()
    duplicates = []

    for param in ignore_params_list:
        if param in parameters:
            parameters.pop(param)

    for running_build in running_builds:
        if running_build['name'] != job_name:
            continue

        diffs = DeepDiff(parameters, running_build['parameters'], ignore_order=True,
                            ignore_string_type_changes=True)
        
        if not diffs:
            duplicates.append(running_build)
    return duplicates

def job_name_from_url(jenkins_server, url):
    return url.replace("{}/job/".format(jenkins_server), "").strip("/")

if __name__ == "__main__":
    options = parse_arguments()

    cluster = Cluster('couchbase://{}'.format(options.server), ClusterOptions(
        PasswordAuthenticator(options.username, options.password)), lockmode=LockMode.WAIT)

    server = connect_to_jenkins(options.build_url_to_check)

    query = "select component, subcomponent, failCount, url, build_id, `build` from server where `build` in {} and url like '{}/job/%'".format(
        options.previous_builds, options.build_url_to_check)

    if options.aborted:
        query += " and result = 'ABORTED'"

    if options.failed:
        query += " and failCount > 0"

    if options.os:
        query += " and lower(os) in {}".format(options.os)

    logger.info(query)

    # get all jobs that match the options (e.g. with failed tests)
    rows = cluster.query(query).rows()

    running_builds = get_running_builds(server)

    for row in rows:

        job_name = job_name_from_url(options.build_url_to_check, row['url'])

        try:

            parameters = parameters_for_job(job_name, row['build_id'], row['build'])

            if options.components:
                if "component" not in parameters:
                    continue

                if parameters['component'] not in options.components:
                    continue

            if options.subcomponents:
                if "subcomponent" not in parameters:
                    continue

                if parameters['subcomponent'] not in options.subcomponents:
                    continue

            logger.info("{}{} {} failures".format(row['url'], row['build_id'], row['failCount']))

            if 'dispatcher_params' not in parameters:

                # only run dispatcher jobs
                if options.dispatcher_jobs:
                    continue

                parameters['version_number'] = options.build

                build_url = server.build_job_url(job_name, parameters=parameters)

                logger.info("Build URL: {}\n".format(build_url))

            else:
                dispatcher_params = json.loads(
                    parameters['dispatcher_params'][11:])

                duplicates = get_duplicate_jobs(running_builds, job_name, parameters)

                if len(duplicates) > 0:
                    if options.stop:
                        for build in duplicates:
                            logger.info(
                                "stopping {}/{}".format(build['name'], build['number']))
                            # server.stop_build(build['name'], build['number'])
                    else:
                        continue

                # This is not needed because the executor is defined at the test level in QE-Test-Suites using the framwork key
                # e.g. -jython, -TAF
                # if job_name != "test_suite_executor":
                #     executor_suffix = job_name.replace("test_suite_executor-", "")
                #     dispatcher_params['executor_suffix'] = executor_suffix

                # if a subcomponent was set then set it for the new dispatcher job
                # TODO: Collate all of the dispatcher jobs that have the same parameters except subcomponent and put them in one dispatcher job
                if parameters["component"] != "None" and parameters["subcomponent"] != "None":
                    dispatcher_params["subcomponent"] = parameters["subcomponent"]

                # this is a rerun
                dispatcher_params['fresh_run'] = False

                # use the new build version
                dispatcher_params['version_number'] = options.build
                
                # test_suite_dispatcher or test_suite_dispatcher_dynvm
                dispatcher_name = job_name_from_url(options.build_url_to_check, dispatcher_params['dispatcher_url'])

                # invalid parameter
                dispatcher_params.pop("dispatcher_url")

                # check for duplicate dispatcher job
                dispatcher_duplicates = get_duplicate_jobs(running_builds, dispatcher_name, dispatcher_params)

                if len(dispatcher_duplicates) > 0:
                    if options.stop:
                        for build in dispatcher_duplicates:
                            logger.info(
                                "stopping {}/{}".format(build['name'], build['number']))
                            server.stop_build(build['name'], build['number'])
                    else:
                        continue

                build_url = server.build_job_url(dispatcher_name, parameters=dispatcher_params)

                logger.info("Build URL: {}\n".format(build_url))

                if not options.noop:
                    logger.info("dispatching")
                    time.sleep(10)
                    server.build_job("test_suite_dispatcher", parameters=dispatcher_params)

        except Exception as e:
            traceback.print_exc()
            continue
