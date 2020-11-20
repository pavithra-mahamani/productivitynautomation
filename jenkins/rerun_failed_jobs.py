import json
from couchbase.cluster import Cluster, ClusterOptions
from couchbase.auth import PasswordAuthenticator
import sys
from optparse import OptionParser
from jenkins import Jenkins
from jenkinshelper import connect_to_jenkins
import logging
import traceback
from deepdiff import DeepDiff
import requests
import jenkins
import time
import subprocess
import os
import csv

logger = logging.getLogger("rerun_failed_jobs")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

# Differences to the existing rerun script

# Runs are completely dependent on the couchbase bucket containing the runs rather than being hard coded. This means that additional components can be added without modifying this script
# Only a single pass is made whereas the existing script runs forever.
# Filtering is available for components, subcomponents, os
# Strategies such as common failures and failures with a higher failed test count can be used when a comparison build is specified.
# A single jenkins job is used rather than building 100+ test_suite_dispatcher jobs
# Dispatcher and non dispatcher jobs can be rerun (jobs without support for reruns are run with failed and successful tests)
# Dispatcher jobs are run with the same parameters as the fresh run e.g. extra testrunner parameters, gerrit cherrypick
# Won't dispatch if similar job already running with option to stop similar job before dispatching


def parse_arguments():
    parser = OptionParser()
    parser.add_option("-c", "--config", dest="configfile", default=".jenkinshelper.ini",
                      help="Configuration file")
    parser.add_option("-u", "--url", dest="build_url_to_check",
                      default='http://qa.sc.couchbase.com', help="Build URL to check")
    parser.add_option("-n", "--noop", dest="noop",
                      help="Just print hanging jobs, don't stop them", action="store_true")

    parser.add_option("-a", "--aborted", dest="aborted",
                      help="Include aborted jobs even with no failed tests", action="store_true")

    parser.add_option("-s", "--stop", dest="stop",
                      help="Stop a duplicate running job before starting the rerun", action="store_true")

    parser.add_option("-f", "--failed", dest="failed",
                      help="Include jobs with failed tests", action="store_true")

    parser.add_option("-p", "--previous-builds", dest="previous_builds",
                      help="Previous builds to compare for regressions or common failures")

    parser.add_option("-b", "--build", dest="build",
                      help="Build version to rerun e.g. 7.0.0-3594")

    parser.add_option("--server", dest="server",
                      help="Couchbase server host", default="172.23.121.84")
    parser.add_option("--username", dest="username",
                      help="Couchbase server username", default="Administrator")
    parser.add_option("--password", dest="password",
                      help="Couchbase server password", default="password")

    parser.add_option("--dispatcher-jobs", dest="dispatcher_jobs",
                      help="only rerun jobs managed by a dispatcher", action="store_true")

    parser.add_option("--os", dest="os",
                      help="List of operating systems: e.g. win, magma, centos, ubuntu, mac, debian, suse, oel")
    parser.add_option("--components", dest="components",
                      help="List of components to include")
    parser.add_option("--subcomponents", dest="subcomponents",
                      help="List of subcomponents to include")
    parser.add_option("--override-executor", dest="override_executor",
                      help="Force passing of -j option to test dispatcher", action="store_true")
    parser.add_option("--s3-logs-url", dest="s3_logs_url", help="Amazon S3 bucket url that stores historical jenkins logs",
                      default="http://cb-logs-qe.s3-website-us-west-2.amazonaws.com")
    parser.add_option("--strategy", dest="strategy",
                      help="Which strategy should be used to find jobs to rerun", choices=("common", "regression"))

    parser.add_option("--pools-threshold", dest="pools_threshold",
                      help="Percent of machines that must be available in each pool before reruns should begin", type="int", default=50)
    parser.add_option("--jobs-threshold", dest="jobs_threshold",
                      help="Percent of jobs that must be complete before reruns should begin", type="int", default=90)

    parser.add_option("--include-pools", dest="include_pools", help="Pools to include in pools-threshold e.g. 12hrreg,magma,regression,os_certification")
    parser.add_option("--exclude-pools", dest="exclude_pools", help="Pools to exclude in pools-threshold e.g. elastic-xdcr")

    parser.add_option("--testrunner_dir", dest="testrunner_dir",
                      help="path to testrunner directory for inline job dispatching", default="../../testrunner")

    parser.add_option("--output", dest="output")

    options, _ = parser.parse_args()

    if not options.build:
        logger.error("No build given")
        sys.exit(1)

    if options.previous_builds:
        options.previous_builds = options.previous_builds.split(",")

    if options.strategy and options.strategy == "regression" and (not options.previous_builds or len(options.previous_builds) != 1):
        logger.error("regression strategy must specify 1 previous build for comparison")
        sys.exit(1)

    if options.previous_builds and not options.strategy:
        logger.error("no strategy specified with previous build")
        sys.exit(1)

    if options.os:
        options.os = options.os.split(",")

    if options.components:
        options.components = options.components.split(",")

    if options.include_pools:
        options.include_pools = options.include_pools.split(",")

    if options.exclude_pools:
        options.exclude_pools = options.exclude_pools.split(",")

    if options.subcomponents:
        if len(options.components) > 1:
            logger.error("Can't supply multiple components with subcomponents")
            sys.exit(1)
        options.subcomponents = options.subcomponents.split(",")

    logger.info("Given build url={}".format(options.build_url_to_check))

    return options


def parameters_for_job(server: Jenkins, name, number, version_number=None, s3_logs_url=None):
    try:
        info = server.get_build_info(name, number)
    except jenkins.JenkinsException:
        if version_number and s3_logs_url:
            info = requests.get("{}/{}/jenkins_logs/{}/{}/jobinfo.json".format(
                s3_logs_url, version_number, name, number)).json()
        else:
            raise ValueError(
                "no version number for build missing from jenkins")
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
        parameters = parameters_for_job(server, build['name'], build['number'])
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

def get_jobs_still_to_run(cluster: Cluster, options):
    query = "SELECT raw name FROM server WHERE `build`= '{}'"
    previous_jobs = set(cluster.query(query.format(options.previous_builds[0])))
    current_jobs = set(cluster.query(query.format(options.build)))
    still_to_run = previous_jobs.difference(current_jobs)

    return previous_jobs, still_to_run


def wait_for_main_run(options, cluster: Cluster):
    WAITING_PATH = "waiting_for_main.csv"

    if options.output:
        waiting_path = os.path.join(options.output, WAITING_PATH)
    else:
        waiting_path = WAITING_PATH

    with open(waiting_path, 'w') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(["completed_jobs", "total_jobs", "unavailable_pools"])

    ready_for_reruns = False

    while not ready_for_reruns:

        ready_for_reruns = True

        try:
            previous_jobs, still_to_run = get_jobs_still_to_run(cluster, options)

            if len(previous_jobs) > 0:
                percent_jobs_complete = ((len(previous_jobs) - len(still_to_run)) / len(previous_jobs)) * 100
            else:
                percent_jobs_complete = 100

            if percent_jobs_complete < options.jobs_threshold:
                ready_for_reruns = False

            if options.include_pools:
                all_pools = options.include_pools
            else:
                pools = cluster.query("select raw poolId from `QE-server-pool` where poolId is not missing and poolId is not null group by poolId")
                all_pools = set()

                for pool in pools:
                    if isinstance(pool, list):
                        for p in pool:
                            all_pools.add(p)
                    else:
                        all_pools.add(pool)

                if options.exclude_pools:
                    for pool in options.exclude_pools:
                        if pool in all_pools:
                            all_pools.remove(pool)

            query = "select count(*) as count from `QE-server-pool` where state = '{0}' and (poolId = '{1}' or '{1}' in poolId)"

            unavailable_pools = []

            # if pools > threshold percent available then main run finishing
            for pool in all_pools:
                available = list(cluster.query(query.format(
                    "available", pool)))[0]['count']

                booked = list(cluster.query(query.format(
                    "booked", pool)))[0]['count']

                total = available + booked

                if total == 0:
                    continue

                percent_available = (available/total) * 100

                logger.info(
                    "{} {:.2f}% available".format(pool, percent_available))

                if percent_available < options.pools_threshold:
                    ready_for_reruns = False
                    unavailable_pools.append(pool)

            if ready_for_reruns:
                break
            else:
                logger.info("Waiting for main run to near completion: {} out of {} jobs ({:.2f}%) complete, {} pool{} unavailable {}".format(len(previous_jobs) - len(still_to_run), len(previous_jobs), percent_jobs_complete, len(unavailable_pools), "" if len(unavailable_pools) == 1 else "s", unavailable_pools))
                with open(waiting_path, 'a') as csvfile:
                    csv_writer = csv.writer(csvfile)
                    csv_writer.writerow([len(previous_jobs) - len(still_to_run), len(previous_jobs), ",".join(unavailable_pools)])

        except Exception:
            traceback.print_exc()
            ready_for_reruns = False

        time.sleep(5)


def run_test_dispatcher(cmd, testrunner_dir):
    subprocess.call(cmd, shell=True, cwd=testrunner_dir)

def filter_query(query: str, options):
    # options.failed -> failures or no tests passed
    # options.aborted -> result is aborted

    filter = None

    if options.failed and options.aborted:
        filter = "(failCount > 0 OR failCount = totalCount OR result = 'ABORTED')"
    elif options.failed:
        filter = "(failCount > 0 OR failCount = totalCount)"
    elif options.aborted:
        filter = "result = 'ABORTED'"

    if filter:
        query += " AND {}".format(filter)

    if options.os:
        query += " AND LOWER(os) in {}".format(options.os)

    return query

def all_failed_jobs(cluster: Cluster, options):
    query = "SELECT `build`, build_id, component, failCount, name, os, result, totalCount, url FROM server WHERE `build` = '{}' AND url LIKE '{}/job/%'".format(options.build, options.build_url_to_check)
    query = filter_query(query, options)

    logger.info("running query {}".format(query))

    jobs = list(cluster.query(query))

    return jobs

def filter_jobs(jobs, cluster: Cluster, server: Jenkins, options, already_rerun):
    running_builds = get_running_builds(server)
    filtered_jobs = []
    for job in jobs:
        if job['name'] in already_rerun:
            continue

        try:
            job_name = job_name_from_url(options.build_url_to_check, job['url'])

            parameters = parameters_for_job(server,
                job_name, job['build_id'], job['build'], options.s3_logs_url)

            # only run dispatcher jobs
            if "dispatcher_params" not in parameters and options.dispatcher_jobs:
                continue

            duplicates = get_duplicate_jobs(
                    running_builds, job_name, parameters)

            if len(duplicates) > 0:
                if options.stop:
                    for build in duplicates:
                        logger.info(
                            "aborting {}/{}".format(build['name'], build['number']))
                        if not options.noop:
                            server.stop_build(build['name'], build['number'])
                else:
                    continue

            if options.components:
                if "component" in parameters and parameters['component'] not in options.components:
                    continue

                if job['component'].lower() not in options.components:
                    continue

            if options.subcomponents and ("subcomponent" not in parameters or parameters['subcomponent'] not in options.subcomponents):
                continue

            if options.strategy:

                if options.strategy == "common":
                    query = "select raw count(*) from server where name = '{}' and `build` in {}".format(job['name'], options.previous_builds)
                    query = filter_query(query, options)
                    common_count = list(cluster.query(query))[0]
                    
                    # job wasn't common across all previous builds
                    if common_count != len(options.previous_builds):
                        continue

                elif options.strategy == "regression":
                    # regression (if name in previous build and failCount or totalCount was different)

                    query = "select failCount, totalCount from server where `build` = '{}' and name = '{}'".format(options.previous_builds[0], job['name'])
                    previous_job = list(cluster.query(query))
                    # if no previous job then this is either a new job or 
                    # that job wasn't run last time so don't filter
                    if len(previous_job) == 1 and int(previous_job[0]['failCount']) == int(job['failCount']) and int(previous_job[0]['totalCount']) == int(job['failCount']):
                        continue

            filtered_jobs.append(job)

        except Exception:
            traceback.print_exc()
            continue

    return filtered_jobs

def rerun_jobs(jobs, server: Jenkins, options):
    already_dispatching = {}

    for job in jobs:
        job_name = job_name_from_url(options.build_url_to_check, job['url'])

        try:

            parameters = parameters_for_job(server,
                job_name, job['build_id'], job['build'], options.s3_logs_url)

            if 'dispatcher_params' not in parameters:

                if not options.noop:
                    server.build_job(job_name, parameters)

            else:

                dispatcher_params = json.loads(
                    parameters['dispatcher_params'][11:])

                # This is not needed because the executor is defined at the test level in QE-Test-Suites using the framwork key
                # e.g. -jython, -TAF

                if options.override_executor and job_name != "test_suite_executor":
                    executor_suffix = job_name.replace(
                        "test_suite_executor-", "")
                    dispatcher_params['executor_suffix'] = executor_suffix

                # can only be a rerun if the job ran to completion
                if job['result'] != "ABORTED":
                    # this is a rerun
                    dispatcher_params['fresh_run'] = False

                dispatcher_name = job_name_from_url(options.build_url_to_check, dispatcher_params['dispatcher_url'])

                # invalid parameter
                dispatcher_params.pop("dispatcher_url")

                # we determine component and subcomponent by the params of the job not dispatcher job
                # e.g. only 1 subcomponent might need to be rerun
                dispatcher_params["component"] = "None"
                dispatcher_params["subcomponent"] = "None"

                if dispatcher_name not in already_dispatching:
                    already_dispatching[dispatcher_name] = {}
                already_dispatching_job = already_dispatching[dispatcher_name]

                if parameters['component'] not in already_dispatching_job:
                    already_dispatching_job[parameters['component']] = []
                already_dispatching_component = already_dispatching_job[parameters['component']]

                found = False
                for subcomponents in already_dispatching_component:
                    if subcomponents['params'] == dispatcher_params:
                        found = True
                        if parameters['subcomponent'] not in subcomponents['subcomponents']:
                            subcomponents['subcomponents'].append(
                                parameters['subcomponent'])

                if not found:
                    already_dispatching_component.append({
                        "params": dispatcher_params,
                        "subcomponents": [parameters['subcomponent']]
                    })
        
        except Exception:
            traceback.print_exc()
            continue

    for [dispatcher_name, components] in already_dispatching.items():
        for [component_name, component] in components.items():
            for job in component:
                try:
                    dispatcher_params = job['params']
                    dispatcher_params['component'] = component_name
                    dispatcher_params['subcomponent'] = ",".join(
                        job['subcomponents'])

                    if not options.noop:
                        server.build_job(dispatcher_name, dispatcher_params)
                except:
                    traceback.print_exc()
                    continue



if __name__ == "__main__":
    options = parse_arguments()

    cluster = Cluster('couchbase://{}'.format(options.server), ClusterOptions(PasswordAuthenticator(options.username, options.password)))

    if options.previous_builds:
        wait_for_main_run(options, cluster)

    server = connect_to_jenkins(options.build_url_to_check)

    already_rerun = []

    # timeout after 20 hours
    timeout = time.time() + (20 * 60 * 60)

    RERUNS_PATH = "reruns.csv"

    if options.output:
        reruns_path = os.path.join(options.output, RERUNS_PATH)
    else:
        reruns_path = RERUNS_PATH

    with open(reruns_path, 'w') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(["name"])

    while True:

        jobs = all_failed_jobs(cluster, options)
        jobs = filter_jobs(jobs, cluster, server, options, already_rerun)

        if len(jobs) > 0:
            rerun_jobs(jobs, server, options)

        with open(reruns_path, 'a') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_rows = []
            for job in jobs:
                csv_rows.append([job['name']])
            csv_writer.writerows(csv_rows)

        if options.previous_builds:
            already_rerun.extend([job['name'] for job in jobs])
            _, still_to_run = get_jobs_still_to_run(cluster, options)
            if time.time() > timeout or len(still_to_run) == 0:
                break
        else:
            break

        time.sleep(5)