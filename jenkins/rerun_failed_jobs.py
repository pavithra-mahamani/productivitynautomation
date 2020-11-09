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
    parser.add_option("-y", "--components", dest="components",
                      help="Regex of components to include")

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


def parameters_for_job(name, number):
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
    return parameters


if __name__ == "__main__":
    options = parse_arguments()

    cluster = Cluster('couchbase://{}'.format(options.server), ClusterOptions(
        PasswordAuthenticator(options.username, options.password)), lockmode=LockMode.WAIT)

    server = connect_to_jenkins(options.build_url_to_check)

    query = "select component, subcomponent, failCount, url, build_id from server where `build` in {} and url like '{}/job/%'".format(
        options.previous_builds, options.build_url_to_check)

    if options.aborted:
        query += " and result = 'ABORTED'"

    if options.failed:
        query += " and failCount > 0"

    if options.os:
        query += " and lower(os) in {}".format(options.os)

    if options.components:
        query += " and lower(component) in {}".format(options.components)

    print(query)

    # get all jobs that match the options (e.g. with failed tests)
    rows = cluster.query(query).rows()

    # get all running builds so we know if a duplicate job is already running
    running_buils = server.get_running_builds()

    # server.get_running_builds() can take a while so these can be used to cache the value and reuse

    # with open("running_builds.json", 'w') as outfile:
    #     json.dump(running_buils, outfile)

    with open("running_builds.json") as json_file:
        running_builds = json.load(json_file)

    builds_with_params = []

    # these parameters could be different even for duplicate jobs
    ignore_params_list = ["descriptor", "servers", "dispatcher_params", "fresh_run", "rerun_params",
                          "retries", "timeout", "mailing_list", "addPoolServers", "version_number"]

    for build in running_builds:
        parameters = parameters_for_job(build['name'], build['number'])
        for param in ignore_params_list:
            try:
                parameters.pop(param)
            except KeyError:
                pass
        builds_with_params.append({
            "name": build['name'],
            "number": build['number'],
            "parameters": parameters
        })

    for row in rows:

        if options.components and not re.search(options.components, row['component'].lower()):
            continue

        job_name = row['url'].replace(
            "{}/job/".format(options.build_url_to_check), "").strip("/")

        print("{}{} {} failures".format(
            row['url'], row['build_id'], row['failCount']))

        try:

            parameters = parameters_for_job(job_name, row['build_id'])

            if 'dispatcher_params' not in parameters:

                if options.dispatcher_jobs:
                    continue

                if job_name == "test_suite_executor-dynvm":
                    pass
                    # TODO: set rerun parameters

            else:
                dispatcher_params = json.loads(
                    parameters['dispatcher_params'][11:])

                duplicates = []

                for running_build in builds_with_params:
                    if running_build['name'] != job_name:
                        continue

                    diffs = DeepDiff(running_build['parameters'], parameters, ignore_order=True,
                                     ignore_string_type_changes=True)
                    if not diffs:
                        duplicates.append(running_build)

                if len(duplicates) > 0:
                    if options.stop:
                        for build in duplicates:
                            print(
                                "stopping {}/{}".format(build['name'], build['number']))
                            # server.stop_build(build['name'], build['number'])
                    else:
                        continue

                # e.g. -jython, -TAF
                if job_name != "test_suite_executor":
                    executor_suffix = job_name.replace(
                        "test_suite_executor-", "")

                if executor_suffix:
                    dispatcher_params['executor_suffix'] = executor_suffix

                # this is a rerun
                dispatcher_params['fresh_run'] = False
                # use the new build version
                dispatcher_params['version_number'] = options.build
                dispatcher_params.pop("dispatcher_url")  # invalid parameter

                build_url = server.build_job_url(
                    "test_suite_dispatcher", parameters=dispatcher_params)

                print("Build URL: {}\n".format(build_url))

                # if not options.noop:
                #     server.build_job("test_suite_dispatcher", parameters=dispatcher_params)

        except Exception as e:
            traceback.print_exc()
            continue
