
import ast
import time
import sys
import urllib
from datetime import datetime
from optparse import OptionParser

import configparser
from couchbase.n1ql import N1QLQuery
from couchbase.cluster import Cluster
from couchbase.bucket import Bucket
from couchbase.cluster import PasswordAuthenticator
from couchbase.exceptions import HTTPError
import requests
import json
from threading import Thread
import threading
from typing import List, Any
import logging

"""
*** QE Rerun Test jenkins jobs : ***
The goal is to run mainly the jobs with test failures and run only the the failed tests count than 
all tests.

The general configuration should be read from configuration file such as .rerunjobs.ini and 
should work on any dispatcher jobs. Include or exclude the jobs using job path prefix.

- queue of all failed jobs
- queue and trigger per component
- don't run any job that is running
- run only failed jobs - with retry failed only
- checks if at least 10 (configurable) machines available 
- Use the new greenboard eventing document as the source.

Below is the previous logic on finding and scheduling the jobs and might need refinement. 
(Ref previous code: https://github.com/girishmind/rerun-failed-jobs)
# Query couchbase to get jobs that have result=FAILURE. Add them to the rerun queue
# Query couchbase to get jobs that have result=Aborted or unstable and failcount=totalcount. Add them to the rerun queue
# Query couchbase to get jobs that have result=Unstable. Fetch the failcount for these jobs from the last weekly build, and compare with the current ones. If there are
#    more failures this week, add them to the rerun queue


# Sort the re-run queue by components, and identify components and subcomponents
# Until all jobs are run do the following :
# Check if there are more than 10 available machines in the server pool
# Trigger jobs per component. Wait for (no. of jobs x 30s + 60s)
# Check if there are more than 10 available machines in the server pool
# Periodically check for any new jobs from the above criteria added to the queue

# Once a job in the queue is executed, create a record in a couchbase bucket to capture the job name, original results and url so that its failures can be analyzed later


"""

MAX_RETRIES = 3
COOLDOWN = 3
MAX_RERUN = 3
MAX_AVAILABLE_VMS_TO_RERUN = 10
RETRY_INTERVAL_SECS = 1200
LOCKMODE_WAIT = 100

GREENBOARD_DB_HOST = "172.23.98.63"
GREENBOARD_DB_USERNAME = "Administrator"
GREENBOARD_DB_PASSWORD = None
GREENBOARD_DB_BUCKETNAME = "server"
RERUN_JOBS_HISTORY_BUCKETNAME = "rerun_jobs"

SERVER_POOL_DB_HOST = "172.23.105.177"
SERVER_POOL_DB_USERNAME = "Administrator"
SERVER_POOL_DB_PASSWORD = None
SERVER_POOL_DB_BUCKETNAME = "QE-server-pool"

components = []
current_build_num = None
prev_stable_build_num = None
run_infinite = None
branch = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)
timestamp = str(datetime.now().strftime('%Y%m%dT_%H%M%S'))
fh = logging.FileHandler("./{}-{}.log".format("rerunjobs", timestamp))
fh.setFormatter(formatter)
logger.addHandler(fh)

CONFIG_FILE = '.rerunjobs.ini'

print("*** QE Rerunning of Jobs ***")

#

class GenericOps(object):
    def __init__(self, bucket):
        self.bucket = bucket

    def close_bucket(self):
        self.bucket._close()

    def run_query(self, query):

        # Add retries if the query fails due to intermittent network issues
        result = []
        CURR_RETRIES = 0
        while CURR_RETRIES < MAX_RETRIES:
            try:
                row_iter = self.bucket.n1ql_query(N1QLQuery(query))
                if row_iter:
                    for row in row_iter:
                        row = ast.literal_eval(json.dumps(row))
                        result.append(row)
                    break
                return result
            except HTTPError as e:
                logger.info(str(e))
                logger.info('Retrying query...')
                time.sleep(COOLDOWN)
                CURR_RETRIES += 1
                pass
            if CURR_RETRIES == MAX_RETRIES:
                raise Exception('Unable to query the Couchbase server...')
        return result


class GreenBoardCluster(GenericOps):

    def __init__(self):
        self.greenboard_cluster = Cluster('couchbase://%s:%s' % (GREENBOARD_DB_HOST, "8091"))
        self.greenboard_authenticator = PasswordAuthenticator(GREENBOARD_DB_USERNAME, GREENBOARD_DB_PASSWORD)
        self.greenboard_cluster.authenticate(self.greenboard_authenticator)

    def get_greenboard_cluster(self):
        return self.get_greenboard_cluster()


class GreenBoardBucket(GreenBoardCluster):

    def __init__(self):
        GreenBoardCluster.__init__(self)

    def get_greenboard_bucket(self):
        self.bucket = self.greenboard_cluster.open_bucket(GREENBOARD_DB_BUCKETNAME, lockmode=LOCKMODE_WAIT)
        return self.bucket

    def run_query(self, query):
        self.get_greenboard_bucket()
        results = super(GreenBoardBucket, self).run_query(query)
        self.close_bucket()
        return results


class GreenBoardHistoryBucket(GreenBoardCluster):

    def __init__(self):
        GreenBoardCluster.__init__(self)

    def get_reun_job_db(self):
        self.bucket = self.greenboard_cluster.open_bucket(RERUN_JOBS_HISTORY_BUCKETNAME, lockmode=LOCKMODE_WAIT)
        return self.bucket

    def run_query(self, query):
        self.get_reun_job_db()
        results = super(GreenBoardHistoryBucket, self).run_query(query)
        self.close_bucket()
        return results


class ServerPoolCluster(GenericOps):

    def __init__(self):
        pass

    def get_server_pool_db(self):
        self.bucket = Bucket('couchbase://' + SERVER_POOL_DB_HOST + '/QE-Test-Suites?operation_timeout=60', lockmode=LOCKMODE_WAIT)
        return self.bucket

    def run_query(self, query):
        self.get_server_pool_db()
        results = super(ServerPoolCluster, self).run_query(query)
        self.close_bucket()
        return results


class RerunFailedJobs:

    rerun_jobs_queue = None  # type: List[Any]

    def __init__(self):

        self.green_board_bucket = GreenBoardBucket()
        self.server_pool_cluster = ServerPoolCluster()
        self.green_board_history_bucket = GreenBoardHistoryBucket()

        # Initialize the job run queue
        self.rerun_jobs_queue = []
        self._lock_queue = threading.Lock()

    def find_jobs_to_rerun(self):
        """
        1) Query couchbase to get jobs that have result=FAILURE. Add them to the rerun queue
        2) Query couchbase to get jobs that have result=Aborted or unstable and failcount=totalcount.
            Add them to the rerun queue
        3) Query couchbase to get jobs that have result=Unstable. Fetch the failcount for these jobs from
            the last weekly build, and compare with the current ones. If there are
            more failures this week, add them to the rerun queue
        :return: jobs_to_rerun
        """
        jobs_to_rerun = []
        all_results = []

        query_include_str, query_exclude_str, rerun_parameters = load_rerun_params()
        if current_build_num == prev_stable_build_num:
            query = "select `build`, name,component,failCount,totalCount,build_id,url||tostring(" \
                    "build_id) as full_url, \
                               'job failed' as reason from {} where `build`='{}'\
                               and lower(os)='centos' and failCount>0 {} {} order by " \
                    "name;".format(
                GREENBOARD_DB_BUCKETNAME, current_build_num, query_include_str, query_exclude_str)

            logger.info("Running query : %s" % query)
            results = self.green_board_bucket.run_query(query)
            all_results.extend(results)
        else:
            #query = "select `build`, name,component,failCount,totalCount,build_id,url||tostring(build_id) as full_url, \
            #        'job failed' as reason from {0} where `build`='{1}'\
            #        and lower(os)='centos' and result='FAILURE' and ( url like '%test_suite_executor-jython/%' or url like \
            #        '%test_suite_executor-TAF/%' or url like '%test_suite_executor/%') \
            #        and name not like 'centos-rqg%' order by name;".format(GREENBOARD_DB_BUCKETNAME, current_build_num)
            query = "select `build`, name,component,failCount,totalCount,build_id,url||tostring(build_id) as full_url, \
                    'job failed' as reason from {} where `build`='{}'\
                    and lower(os)='centos' and result='FAILURE' {} {} order by name;".format(
                GREENBOARD_DB_BUCKETNAME, current_build_num, query_include_str, query_exclude_str)


            logger.info("Running query : %s" % query)
            results = self.green_board_bucket.run_query(query)
            all_results.extend(results)

            #query = "select `build`,name,component,failCount,totalCount,build_id,url||tostring(build_id) as full_url, \
            #        '0 tests passed' as reason from {0} where `build`='{1}'\
            #        and lower(os)='centos' and result in ['UNSTABLE','ABORTED'] and failCount=totalCount\
            #        and name not like 'centos-rqg%' and ( url like '%test_suite_executor-jython/%' or url like '%test_suite_executor-TAF/%' or url like '%test_suite_executor/%') order by name;".format(
            #    GREENBOARD_DB_BUCKETNAME, current_build_num)
            query = "select `build`,name,component,failCount,totalCount,build_id,url||tostring(build_id) as full_url, \
                    '0 tests passed' as reason from {} where `build`='{}'\
                    and lower(os)='centos' and result in ['UNSTABLE','ABORTED'] and " \
                    "failCount=totalCount {} {} " \
                    "order by name;".format( GREENBOARD_DB_BUCKETNAME, current_build_num,
                                             query_include_str, query_exclude_str)
            logger.info("Running query : %s" % query)
            results = self.green_board_bucket.run_query(query)
            all_results.extend(results)

            query_include_str1, query_exclude_str1, _ = load_rerun_params("s1")
            query_include_str2, query_exclude_str2, _ = load_rerun_params("s2")

            #query = "select s1.`build`,s1.name, s1.component, s1.failCount, s1.totalCount, s1.build_id, s1.url || tostring(s1.build_id) \
            #        as full_url, 'more failures than {2}' as reason from {0} s1 left outer join {0} s2 on s1.name = s2.name\
            #        and s2. `build` = '{2}' \
            #        and lower(s2.os) = 'centos' and ( s2.url like '%test_suite_executor-jython/%' or s2.url like '%test_suite_executor-TAF/%' or s2.url like '%test_suite_executor/%') \
            #        and s2.name not like 'centos-rqg%' where s1.`build` = '{1}' and lower(s1.os) = 'centos' \
            #        and s1.result = 'UNSTABLE' and ( s1.url like '%test_suite_executor-jython/%' or s1.url like '%test_suite_executor-TAF/%' or s1.url like '%test_suite_executor/%') and s1.name not like 'centos-rqg%'\
            #        and (s1.failCount - s2.failCount) > 0 order by s1.name".format(GREENBOARD_DB_BUCKETNAME,
            #                                                                       current_build_num, prev_stable_build_num)
            query = "select s1.`build`,s1.name, s1.component, s1.failCount, s1.totalCount, s1.build_id, s1.url || tostring(s1.build_id) \
                    as full_url, 'more failures than {2}' as reason from {0} s1 left outer join {0} s2 on s1.name = s2.name\
                    and s2. `build` = '{2}' \
                    and lower(s2.os) = 'centos' {3} {4} where s1.`build` = '{1}' and lower(s1.os) = " \
                    "'centos' \
                    and s1.result = 'UNSTABLE' {5} {6}\
                    and (s1.failCount - s2.failCount) > 0 order by s1.name".format(
                        GREENBOARD_DB_BUCKETNAME, current_build_num, prev_stable_build_num,
                        query_include_str1, query_exclude_str1, query_include_str2, query_exclude_str2)


            logger.info("Running query : %s" % query)
            results = self.green_board_bucket.run_query(query)
            all_results.extend(results)

        for job in all_results:
            if not self.to_be_filtered(job):
                logger.info(job)
                jobs_to_rerun.append(job)

        return jobs_to_rerun

    def to_be_filtered(self, job):
        """
        Remove jobs from the list if :
        1) Same job (unique build_id, job name) is already queued up
        2) Same job (unique build_id, job name) was already re-run (might be still running)
        3) Same job (job name) has been re-run MAX_RERUN times.
        """

        component, subcomponent = self.process_job_name(job)

        if len([i for i in self.rerun_jobs_queue if
                (i['component'] == component and i['subcomponent'] == subcomponent)]) != 0:
            return True

        query = "select raw count(*) from {0} where `build`='{1}' and build_id={2} and name='{3}'".format(
            RERUN_JOBS_HISTORY_BUCKETNAME, current_build_num, job['build_id'], job['name'])
        count = int(self.green_board_history_bucket.run_query(query)[0])
        if count > 0:
            return True

        query = "select raw count(*) from {0} where `build`='{1}' and name='{2}'".format(
            RERUN_JOBS_HISTORY_BUCKETNAME, current_build_num, job['name'])
        count = int(self.green_board_history_bucket.run_query(query)[0])
        if count > MAX_RERUN:
            return True

        return False

    def process_job_name(self, job):
        comp_subcomp = job['name'][7:]
        tokens = comp_subcomp.split("_", 2)
        if tokens[0] in ["backup", "cli"]:
            if (tokens[0] == "backup" and tokens[1] == "recovery") or (
                    tokens[0] == "cli" and tokens[1] == "imex") or (
                    tokens[0] == "cli" and tokens[1] == "tools"):
                component = tokens[0] + "_" + tokens[1]
                subcomponent = "_".join(tokens[2:])
            else:
                component = tokens[0]
                subcomponent = "_".join(tokens[1:])
        else:
            component = tokens[0]
            subcomponent = "_".join(tokens[1:])

        return component, subcomponent

    def save_rerun_job_history(self, job):
        iteration = self.get_iteration(job)
        doc_name = job['name'] + "_" + job['build'] + "_" + str(iteration)
        job["timestamp"] = datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
        self.green_board_history_bucket.get_reun_job_db().upsert(doc_name, job)
        self.green_board_history_bucket.close_bucket()

    def get_iteration(self, job):
        query = "select raw count(*) from {0} where `build`='{1}' and name='{2}'".format(
            RERUN_JOBS_HISTORY_BUCKETNAME, current_build_num, job['name'])
        count = int(self.green_board_history_bucket.run_query(query)[0])
        return count+1

    def manage_rerun_jobs_queue(self, jobs_to_rerun):
        rerun_job_details = []
        for job in jobs_to_rerun:
            component, subcomponent = self.process_job_name(job)
            job["component"] = component
            job["subcomponent"] = subcomponent
            rerun_job_details.append(job)

        with self._lock_queue:
            self.rerun_jobs_queue.extend(rerun_job_details)
            logger.info("current rerun job queue")
            self.print_current_queue()

    def print_current_queue(self):
        logger.info("========================================")
        for job in self.rerun_jobs_queue:
            logger.info("||" + job["component"] + " " + job["subcomponent"] + "||")
        logger.info("========================================")

    def get_available_serverpool_machines(self, poolId):
        query = "SELECT raw count(*) FROM `{0}` where state ='available' and os = 'centos' and \
                (poolId = '{1}' or '{1}' in poolId)".format(
            SERVER_POOL_DB_BUCKETNAME, poolId)
        logger.info("Running query : %s" % query)
        available_vms = self.server_pool_cluster.run_query(query)[0]
        logger.info("number of available machines : {0}".format(available_vms))
        return available_vms

    def form_rerun_job_matrix(self):
        rerun_job_matrix = {}
        for job in self.rerun_jobs_queue:
            comp = job["component"]
            if comp == "-os":
                continue
            if comp in rerun_job_matrix.keys():
                comp_details = rerun_job_matrix[comp]
                sub_component_list = comp_details["subcomponent"]
                if job["subcomponent"] not in sub_component_list:
                    sub_component_list = sub_component_list + "," + job["subcomponent"]
                    count = comp_details["count"] + 1
            else:
                rerun_job_matrix[comp] = {}
                sub_component_list = job["subcomponent"]
                count = 1
            rerun_job_matrix[comp]["subcomponent"] = sub_component_list
            rerun_job_matrix[comp]["poolId"] = next(item for item in components if item["name"] == comp)["poolId"]
            rerun_job_matrix[comp]["addPoolId"] = next(item for item in components if item["name"] == comp)["addPoolId"]
            rerun_job_matrix[comp]["count"] = count
            rerun_job_matrix[comp]["url"] = job["full_url"]

        logger.info("current rerun_job_matrix")
        for comp in rerun_job_matrix:
            logger.info(comp + " || " + str(rerun_job_matrix[comp]))

        return rerun_job_matrix

    def trigger_jobs(self):
        """
        1. Get the number of available machines in the regression queue
        2. If available number > 10, then start with one component in the queue and save job history.
        3. Call test_suite_dispatcher job for that component.
        4. Wait for (no. of jobs to be rerun * 40s) + 1m
        Repeat #1-4

        wget "http://qa.sc.couchbase.com/job/test_suite_dispatcher/buildWithParameters?token=extended_sanity&OS=centos&version_number=$version_number&suite=12hour&component=subdoc,xdcr,rbac,query,nserv,2i,eventing,backup_recovery,sanity,ephemeral,epeng&url=$url&serverPoolId=regression&branch=$branch"
        """
        logger.info("trigger_jobs: current job queue")
        self.print_current_queue()
        if self.rerun_jobs_queue:
            rerun_job_matrix = self.form_rerun_job_matrix()
            logger.info(rerun_job_matrix)
            for comp in rerun_job_matrix:
                sleep_time = 60
                comp_rerun_details = rerun_job_matrix.get(comp)
                logger.info("processing : {0} : {1}".format(comp, comp_rerun_details))
                pool_id = comp_rerun_details["poolId"]
                available_vms = self.get_available_serverpool_machines(pool_id)
                _, _, rerun_parameters = load_rerun_params()
                source_job = "test_suite_dispatcher_testreruns"
                include_list = dict(read_config()["includes"])
                for key in include_list:
                    if key.startswith("url."):
                        job_name = key.split(".")[1].replace("%","")
                        logger.info("job_name={}".format(job_name))
                        if job_name in comp_rerun_details["url"]:
                            source_job = include_list[key]
                            rerun_parameters += "&rerun_params=" + urllib.parse.quote(
                                "-d  failed={}".format(comp_rerun_details["url"]))
                            break

                url = "http://qa.sc.couchbase.com/job/{10}/buildWithParameters?" \
                      "token={0}&OS={1}&version_number={2}&suite={3}&component={4}&subcomponent={5}" \
                      "&serverPoolId={6}&branch={7}&addPoolId={8}{9}". \
                    format("extended_sanity", "centos", current_build_num, "12hr_weekly",
                           comp, comp_rerun_details["subcomponent"], comp_rerun_details["poolId"],
                           branch, comp_rerun_details["addPoolId"], rerun_parameters, source_job)
                logger.info("Waiting to trigger job with URL " + str(url))
                if available_vms >= MAX_AVAILABLE_VMS_TO_RERUN:
                    logger.info("Trigerring..")
                    response = requests.get(url, verify=True)
                    #response = None
                    if not response or not response.ok:
                        logger.error("Error in triggering job")
                        logger.error(str(response))
                    else:
                        for job in self.rerun_jobs_queue:
                            if job["component"] == comp:
                                self.save_rerun_job_history(job)

                        with self._lock_queue:
                            self.rerun_jobs_queue[:] = [job for job in self.rerun_jobs_queue if job.get('component') != comp]
                        sleep_time = (comp_rerun_details["count"] * 40) + 60
                    logger.info("sleeping for {0} before triggering again".format(sleep_time))
                else:
                    logger.info("Number of available VMS: {}".format(available_vms))
                logger.info("Sleeping for {} secs".format(sleep_time))
                time.sleep(sleep_time)

    def trigger_jobs_constantly(self):
        logger.info("trigger_jobs...")
        while run_infinite == "True" or self.rerun_jobs_queue:
            time.sleep(40)
            self.trigger_jobs()

        logger.info("stopping triggering jobs as job queue is empty")

    def find_and_manage_rerun_jobs(self):
        jobs_to_rerun = self.find_jobs_to_rerun()
        self.manage_rerun_jobs_queue(jobs_to_rerun)
        while run_infinite == "True" or self.rerun_jobs_queue:
            jobs_to_rerun = self.find_jobs_to_rerun()
            self.manage_rerun_jobs_queue(jobs_to_rerun)
            logger.info("sleeping for {} secs before triggering again".format(RETRY_INTERVAL_SECS))
            time.sleep(RETRY_INTERVAL_SECS)

        logger.info("stopping monitoring")

def read_config():
    config = configparser.RawConfigParser()
    config.read(CONFIG_FILE)
    logger.info(config.sections())
    return config

def load_config():
    logger.info("Loading config from {}".format(CONFIG_FILE))
    config = read_config()

    global MAX_RETRIES, COOLDOWN, MAX_RERUN, MAX_AVAILABLE_VMS_TO_RERUN, RETRY_INTERVAL_SECS
    MAX_RETRIES = int(config.get("common", "MAX_RETRIES"))
    COOLDOWN = int(config.get("common", "COOLDOWN"))
    MAX_RERUN = int(config.get("common", "MAX_RERUN"))
    MAX_AVAILABLE_VMS_TO_RERUN = int(config.get("common", "MAX_AVAILABLE_VMS_TO_RERUN"))
    RETRY_INTERVAL_SECS = int(config.get("common", "RETRY_INTERVAL_SECS"))
    logger.info("MAX_RETRIES={}".format(MAX_RETRIES))
    logger.info("MAX_AVAILABLE_VMS_TO_RERUN={}".format(MAX_AVAILABLE_VMS_TO_RERUN))
    logger.info("RETRY_INTERVAL_SECS={}".format(RETRY_INTERVAL_SECS))

    global GREENBOARD_DB_HOST, GREENBOARD_DB_USERNAME, GREENBOARD_DB_PASSWORD, \
        GREENBOARD_DB_BUCKETNAME, RERUN_JOBS_HISTORY_BUCKETNAME
    GREENBOARD_DB_HOST = config.get("greenboard", "GREENBOARD_DB_HOST")
    GREENBOARD_DB_USERNAME = config.get("greenboard", "GREENBOARD_DB_USERNAME")
    GREENBOARD_DB_PASSWORD = config.get("greenboard", "GREENBOARD_DB_PASSWORD")
    GREENBOARD_DB_BUCKETNAME = config.get("greenboard", "GREENBOARD_DB_BUCKETNAME")
    RERUN_JOBS_HISTORY_BUCKETNAME = config.get("greenboard", "RERUN_JOBS_HISTORY_BUCKETNAME")
    logger.info("GREENBOARD_DB_HOST={}".format(GREENBOARD_DB_HOST))
    logger.info("GREENBOARD_DB_USERNAME={}".format(GREENBOARD_DB_USERNAME))
    logger.info("GREENBOARD_DB_BUCKETNAME={}".format(GREENBOARD_DB_BUCKETNAME))
    logger.info("RERUN_JOBS_HISTORY_BUCKETNAME={}".format(RERUN_JOBS_HISTORY_BUCKETNAME))

    global SERVER_POOL_DB_HOST, SERVER_POOL_DB_USERNAME, SERVER_POOL_DB_PASSWORD, \
        SERVER_POOL_DB_BUCKETNAME
    SERVER_POOL_DB_HOST = config.get("serverpool", "SERVER_POOL_DB_HOST")
    SERVER_POOL_DB_USERNAME = config.get("serverpool", "SERVER_POOL_DB_USERNAME")
    SERVER_POOL_DB_PASSWORD = config.get("serverpool", "SERVER_POOL_DB_PASSWORD")
    SERVER_POOL_DB_BUCKETNAME = config.get("serverpool", "SERVER_POOL_DB_BUCKETNAME")
    logger.info("SERVER_POOL_DB_HOST={}".format(SERVER_POOL_DB_HOST))
    logger.info("SERVER_POOL_DB_USERNAME={}".format(SERVER_POOL_DB_USERNAME))
    logger.info("SERVER_POOL_DB_BUCKETNAME={}".format(SERVER_POOL_DB_BUCKETNAME))

    global components
    newcomponents =dict(config["components"])
    for key in newcomponents.keys():
        comp_obj = {}
        comp_obj["name"] = key
        poolId = newcomponents[key].split(".")
        comp_obj["poolId"] = poolId[0]
        if len(poolId) > 1:
            comp_obj["addPoolId"] = poolId[1]
        else:
            comp_obj["addPoolId"] = "None"
        components.append(comp_obj)
    logger.info("components={}".format(components))

def load_rerun_params(prefix=None):
    config = read_config()
    rerunparameters = dict(config["rerunparameters"])
    rerun_str = ""
    index = 1
    for paramkey in rerunparameters:
        rerun_str += "&" + paramkey + "=" + rerunparameters[paramkey]

    includes_list = dict(config["includes"])
    excludes_list = dict(config["excludes"])

    query_include_str = ""
    if len(includes_list)>=1:
        query_include_str=" and ("
    index=1
    for include_key in includes_list:
        if index > 1:
            query_include_str += " or "
        if include_key.startswith("url."):
            if prefix:
                urlprefix = prefix+".url"
            else:
                urlprefix = "url"
            query_include_str += urlprefix + "  like '" + include_key.split(".")[1] + "'"
        elif include_key.startswith("name"):
            if prefix:
                nameprefix = prefix+".name"
            else:
                nameprefix = "name"
            for n in includes_list[include_key].split(","):
                query_include_str += nameprefix + "  like '" + n + "'"
        else:
            if prefix:
                uprefix = uprefix+"." + include_key
            else:
                uprefix = include_key
            for n in includes_list[include_key].split(","):
                query_include_str += uprefix + "  like '" + n + "'"
        index += 1

    if len(includes_list) >= 1:
        query_include_str += ")"
    logger.info("query_include_str={}".format(query_include_str))
    query_exclude_str = ""
    if len(excludes_list)>=1:
        query_exclude_str=" and ("
    index=1
    for exclude_key in excludes_list:
        if index > 1:
            query_exclude_str += " and "
        if exclude_key.startswith("url."):
            if prefix:
                urlprefix = prefix+".url"
            else:
                urlprefix = "url"
            query_exclude_str += urlprefix + " not like '" + exclude_key.split(".")[1] + "'"
        elif exclude_key.startswith("name"):
            if prefix:
                nameprefix = prefix+".name"
            else:
                nameprefix = "name"
            for n in excludes_list[exclude_key].split(","):
                query_exclude_str += nameprefix + "  not like '" + n + "'"
        else:
            if prefix:
                uprefix = uprefix+"." + exclude_key
            else:
                uprefix = exclude_key
            for n in excludes_list[exclude_key].split(","):
                query_exclude_str += uprefix + " not like '" + n + "'"
        index += 1

    if len(excludes_list) >= 1:
        query_exclude_str += ")"
    logger.info("query_exclude_str={}".format(query_exclude_str))
    return query_include_str, query_exclude_str, rerun_str

def parse_arguments():
    parser = OptionParser()
    parser.add_option('-v', '--version', dest='version')
    parser.add_option("-c", "--config", dest="configfile", default=".rerunjobs.ini",
                        help="Configuration file")
    parser.add_option("-l", "--log-level", dest="loglevel", default="INFO",
                        help="e.g -l info,warning,error")
    parser.add_option("-m", "--prevbuild", dest="prev_stable_build_num", help="Previous CB build")
    parser.add_option("-n", "--currbuild", dest="current_build_num", help="Current CB build")
    parser.add_option("-i", "--infinte", dest="run_infinite", default="False", help="Run infinite")
    parser.add_option("-r", "--retries", dest="retries", default="1", help="Number of retries")
    parser.add_option("-p", "--rerunmode", dest="rerunmode", default="failed",
                      help="Rerun params - failed or passed")

    parser.add_option("-b", "--branch", dest="branch", default="master", help="Branch")

    options, args = parser.parse_args()
    global current_build_num, prev_stable_build_num, run_infinite, branch

    if options.current_build_num:
        current_build_num = options.current_build_num
    if options.prev_stable_build_num:
        prev_stable_build_num = options.prev_stable_build_num
    if options.run_infinite:
        run_infinite = options.run_infinite
    if options.branch:
        branch = options.branch
    global MAX_RETRIES, MAX_RERUN
    if options.retries:
        MAX_RETRIES = int(options.retries)
        MAX_RERUN = MAX_RETRIES

    if len(args)==1:
        current_build_num = args[0]
    elif len(args)==2:
        current_build_num = args[0]
        prev_stable_build_num = args[1]
    elif len(args) == 3:
        current_build_num = args[0]
        prev_stable_build_num = args[1]
        run_infinite = args[2]
    elif len(args) == 4:
        current_build_num = args[0]
        prev_stable_build_num = args[1]
        run_infinite = args[2]
        branch = args[3]

    if not current_build_num:
        logger.error("No current CB build given!")
        sys.exit(1)
    elif not prev_stable_build_num:
        prev_stable_build_num = current_build_num

    logger.info("Current build={}".format(current_build_num))
    logger.info("Previous build={}".format(prev_stable_build_num))
    logger.info("Run infinite={}".format(run_infinite))
    logger.info("Branch={}".format(branch))
    return options

def set_log_level(log_level='info'):
    if log_level and log_level.lower() == 'info':
        logger.setLevel(logging.INFO)
    elif log_level and log_level.lower() == 'warning':
        logger.setLevel(logging.WARNING)
    elif log_level and log_level.lower() == 'debug':
        logger.setLevel(logging.DEBUG)
    elif log_level and log_level.lower() == 'critical':
        logger.setLevel(logging.CRITICAL)
    elif log_level and log_level.lower() == 'fatal':
        logger.setLevel(logging.FATAL)
    else:
        logger.setLevel(logging.NOTSET)


if __name__ == '__main__':

    """
    Spawn 2 never ending threads - 1 to populate the re-run queue, other to dispatch jobs
    whenever there are free machines
    """

    load_config()
    options = parse_arguments()
    set_log_level(options.loglevel)
    rerun_inst = RerunFailedJobs()

    get_rerun_job_thread = Thread(target=rerun_inst.find_and_manage_rerun_jobs)
    get_rerun_job_thread.start()

    time.sleep(10)

    trigger_jobs_thread = Thread(target=rerun_inst.trigger_jobs_constantly)
    trigger_jobs_thread.start()
