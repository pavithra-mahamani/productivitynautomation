import couchbase
import json
from couchbase.cluster import Cluster
from couchbase.cluster import PasswordAuthenticator
from couchbase.n1ql import N1QLQuery
import sys
from optparse import OptionParser
from jenkinshelper import connect_to_jenkins
import logging
import traceback
from deepdiff import DeepDiff
import requests
import jenkins
import time
import subprocess
import threading

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

    parser.add_option("-p", "--previous-build", dest="previous_build",
                      help="Previous build to compare for regressions or common failures")

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
    parser.add_option("--dispatch-threshold", dest="dispatch_threshold",
                      help="Percent of servers that must be available before a job should be dispatched", type="int", default=50)
    parser.add_option("--testrunner_dir", dest="testrunner_dir",
                      help="path to testrunner directory for inline job dispatching", default="../../testrunner")

    options, _ = parser.parse_args()

    if not options.build:
        logger.error("No --build given")
        sys.exit(1)

    if options.previous_build and not options.strategy:
        logger.error("no strategy specified with previous build")
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

    logger.info("Given build url={}".format(options.build_url_to_check))

    return options


def parameters_for_job(name, number, version_number=None, s3_logs_url=None):
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


def jobs_to_rerun(cluster, options):
    def filter_single_build(query):
        if options.aborted and options.failed:
            query += " and (result = 'ABORTED' or failCount > 0)"
        else:
            if options.failed:
                query += " and failCount > 0"

            if options.aborted:
                query += " and result = 'ABORTED'"

        if options.os:
            query += " and lower(os) in {}".format(options.os)

        return query

    if options.strategy and options.strategy in ["regression", "common"]:

        if not options.previous_build:
            logger.error(
                "Need previous build for this strategy")
            sys.exit(1)

        query = "select s2.result, s2.component, s2.failCount, s2.url, s2.build_id, s2.`build` from server s1 inner join server s2 on s1.name = s2.name where s1.`build` = '{0}' and s2.`build` = '{1}' and s1.url like '{2}/job/%' and s2.url like '{2}/job/%'".format(
            options.previous_build, options.build, options.build_url_to_check)

        if options.strategy == "regression":

            if options.aborted and options.failed:
                query += " and ((s2.result = 'ABORTED' and s1.result != 'ABORTED') or s2.failCount > s1.failCount)"
            else:
                if options.failed:
                    query += " and s2.failCount > s1.failCount"

                if options.aborted:
                    query += " and s2.result = 'ABORTED' and s1.result != 'ABORTED'"

        elif options.strategy == "common":

            if options.aborted and options.failed:
                query += " and (s2.result = 'ABORTED' or s2.failCount > 0) and (s1.result = 'ABORTED' or s1.failCount > 0)"
            else:
                if options.failed:
                    query += " and s2.failCount > 0 and s1.failCount > 0"

                if options.aborted:
                    query += " and s2.result = 'ABORTED' and s1.result = 'ABORTED'"

        if options.os:
            query += " and lower(s1.os) in {0} and lower(s2.os) in {0}".format(
                options.os)

    else:

        query = "select result, component, failCount, url, build_id, `build` from server where `build` = '{}' and url like '{}/job/%'".format(
            options.build, options.build_url_to_check)

        query = filter_single_build(query)

    logger.info(query)

    rows = list(cluster.n1ql_query(N1QLQuery(query)))

    # also add new failing jobs that weren't present in the last run
    # TODO: can this be done in a better way
    # only applicable when previous build is being compared
    if options.previous_build:
        query = "SELECT result, component, failCount, url, build_id, `build` FROM server WHERE name NOT IN (SELECT RAW name FROM server s WHERE `build` = '{0}' and url like '{1}/job/%' GROUP BY name) AND `build` = '{2}' and url like '{1}/job/%'".format(
            options.previous_build, options.build_url_to_check, options.build)
        query = filter_single_build(query)
        logger.info(query)
        rows.extend(list(cluster.n1ql_query(N1QLQuery(query))))

    return rows


def wait_for_main_run(options):
    cluster = Cluster('couchbase://{}'.format(options.server))
    authenticator = PasswordAuthenticator(options.username, options.password)
    cluster.authenticate(authenticator)
    bucket = cluster.open_bucket('QE-server-pool')
    query = "select count(*) as count from `QE-server-pool` where state = '{0}' and (poolId = '{1}' or '{1}' in poolId)"

    server_pools_available = False

    while not server_pools_available:
        server_pools_available = True

        try:
            # if regression, reg12hrreg, magmareg and os_certification are > threshold percent available then main run finishing
            for pool in ["magmareg", "regression", "12hrreg", "os_certification"]:
                available = list(cluster.n1ql_query(N1QLQuery(query.format(
                    "available", pool))))[0]['count']

                booked = list(cluster.n1ql_query(N1QLQuery(query.format(
                    "booked", pool))))[0]['count']

                total = available + booked
                capacity = (available/total) * 100

                logger.info(
                    "{} pool at {:.2f}% capacity".format(pool, capacity))

                if capacity < options.dispatch_threshold:
                    server_pools_available = False
        except Exception:
            # we could't check so try again
            server_pools_available = False

        if server_pools_available:
            break

        time.sleep(5 * 60)


def run_test_dispatcher(cmd, testrunner_dir):
    subprocess.call(cmd, shell=True, cwd=options.testrunner_dir)


if __name__ == "__main__":
    options = parse_arguments()

    wait_for_main_run(options)

    cluster = Cluster('couchbase://{}'.format(options.server))
    authenticator = PasswordAuthenticator(options.username, options.password)
    cluster.authenticate(authenticator)
    cluster = cluster.open_bucket('server')

    to_rerun = jobs_to_rerun(cluster, options)

    server = connect_to_jenkins(options.build_url_to_check)

    running_builds = get_running_builds(server)

    already_dispatching = {}

    for job in to_rerun:

        job_name = job_name_from_url(options.build_url_to_check, job['url'])

        try:

            parameters = parameters_for_job(
                job_name, job['build_id'], job['build'], options.s3_logs_url)

            if options.components and ("component" not in parameters or parameters['component'] not in options.components):
                continue

            if options.subcomponents and ("subcomponent" not in parameters or parameters['subcomponent'] not in options.subcomponents):
                continue

            logger.info("{}{} {} failures".format(
                job['url'], job['build_id'], job['failCount']))

            if 'dispatcher_params' not in parameters:

                # only run dispatcher jobs
                if options.dispatcher_jobs:
                    continue

                parameters['version_number'] = options.build

                build_url = server.build_job_url(job_name, parameters)
                logger.info("Build URL: {}\n".format(build_url))

            else:
                dispatcher_params = json.loads(
                    parameters['dispatcher_params'][11:])

                if "component" not in parameters or parameters['component'] == "None":
                    continue

                if "subcomponent" not in parameters or parameters['subcomponent'] == "None":
                    continue

                duplicates = get_duplicate_jobs(
                    running_builds, job_name, parameters)

                if len(duplicates) > 0:
                    if options.stop:
                        for build in duplicates:
                            logger.info(
                                "aborting {}/{}".format(build['name'], build['number']))
                            # server.stop_build(build['name'], build['number'])
                    else:
                        continue

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

                # use the new build version
                dispatcher_params['version_number'] = options.build

                # test_suite_dispatcher or test_suite_dispatcher_dynvm
                dispatcher_name = job_name_from_url(
                    options.build_url_to_check, dispatcher_params['dispatcher_url'])

                # invalid parameter
                dispatcher_params.pop("dispatcher_url")

                # check for duplicate dispatcher job
                dispatcher_duplicates = get_duplicate_jobs(
                    running_builds, dispatcher_name, dispatcher_params)

                if len(dispatcher_duplicates) > 0:
                    if options.stop:
                        for build in dispatcher_duplicates:
                            logger.info(
                                "aborting {}/{}".format(build['name'], build['number']))
                            server.stop_build(build['name'], build['number'])
                    else:
                        continue

                # we determine component and subcomponent by the params of the job not dispatcher job
                # e.g. only 1 subcomponent might need to be rerun
                dispatcher_params["component"] = "None"
                dispatcher_params["subcomponent"] = "None"

                if job_name not in already_dispatching:
                    already_dispatching[job_name] = {}
                already_dispatching_job = already_dispatching[job_name]

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

        except Exception as e:
            traceback.print_exc()
            continue

    dispatching_threads = []

    for [dispatcher_name, components] in already_dispatching.items():
        for [component_name, component] in components.items():
            for job in component:

                dispatcher_params = job['params']
                dispatcher_params['component'] = component_name
                dispatcher_params['subcomponent'] = ",".join(
                    job['subcomponents'])

                params = []

                # no launch
                params.append("-n")
                params.append(
                    "--dispatcher_params='{}'".format(json.dumps(dispatcher_params)))

                for [name, value] in dispatcher_params.items():
                    if name == "Test" and value:
                        params.append("-t")

                    if name == "fresh_run" and not value:
                        params.append("-q")

                    if name == "rerun_params" and value != "":
                        params.append("-m '{}'".format(value))

                    if name == "executor_suffix" and value != "":
                        params.append("-j {}".format(value))

                    if name == "check_vm" and value:
                        params.append("--check_vm True")

                    if name == "executor_job_parameters" and value != "":
                        params.append("--job_params {}".format(value))

                    if name == "suite":
                        params.append("-r {}".format(value))

                    if name == "component":
                        params.append("-c {}".format(value))

                    if name == "subcomponent":
                        params.append("-s {}".format(value))

                    if name == "version_number":
                        params.append("-v {}".format(value))

                    if name == "OS":
                        params.append("-o {}".format(value))

                    if name == "serverPoolId":
                        params.append("-p {}".format(value))

                    if name == "addPoolId":
                        params.append("-a {}".format(value))

                    if name == "url" and value != "":
                        params.append("-u {}".format(value))

                    if name == "branch":
                        params.append("-b {}".format(value))

                    if name == "cherrypick" and value != "":
                        params.append("-g '{}'".format(value))

                    if name == "extraParameters" and value != "":
                        params.append("-e {}".format(value))

                    if name == "retries":
                        params.append("-i {}".format(value))

                    # test_suite_dispatcher_dynvm

                    if name == "SERVER_MANAGER_TYPE" and value == "dynamic":
                        params.append(
                            "-j dynvm -x 172.23.104.180:5000 -z 2000")

                        if "CHECK_SSH" in dispatcher_params:
                            params.append(
                                "-w {}".format(dispatcher_params['CHECK_SSH']))

                cmd = "python scripts/testDispatcher.py {}".format(
                    " ".join(params))

                print(cmd)

                thread = threading.Thread(
                    target=run_test_dispatcher, args=(cmd, options.testrunner_dir))
                thread.start()

                dispatching_threads.append(thread)

    for thread in dispatching_threads:
        thread.join()
