import json
from datetime import datetime
import logging
import sys
from optparse import OptionParser

import configparser
import jenkins
from deepdiff import DeepDiff

"""
A simple Jenkins helper tool to do the general activities
   - find if any similar job is running
   - find the list of queued builds
   - find the list of running builds

"""

CONFIG_FILE = ".jenkinshelper.ini"
#server = jenkins.Jenkins('http://qa.sc.couchbase.com', username='qeinfra', password='password')
server = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)
timestamp = str(datetime.now().strftime('%Y%m%dT_%H%M%S'))
fh = logging.FileHandler("./{}-{}.log".format("jenkinshelper", timestamp))
fh.setFormatter(formatter)
logger.addHandler(fh)

def connect_jenkins(jenkins_server_url, jenkins_user, jenkins_user_password):
    global server
    server = jenkins.Jenkins(jenkins_server_url,
                             username=jenkins_user, password=jenkins_user_password)
    return server

def get_jenkins_info():
    user = server.get_whoami()
    version = server.get_version()
    print('Jenkins version: %s, user: %s' % (version, user['fullName']))

def get_slave_nodes(jenkins_server_url):
    server = connect_to_jenkins(jenkins_server_url)
    nodes = server.get_nodes()
    print("Number of slaves={}, {}".format(len(nodes),nodes))
    for n in nodes:
        if "master" != n["name"]:
            node_info = server.get_node_info(n["name"])
            print(node_info)

def get_queued_jobs_list(jenkins_server_url):
    #build_queue = server.get_queue_info()
    #print(build_queue)
    server = connect_to_jenkins(jenkins_server_url)
    builds = server.get_queue_info()
    #print(builds)
    print_builds_detail(builds)


def is_jenkins_job_running(name=None, build=None, ignore_paramers=None):
    new_build_info = server.get_build_info(name, build)
    new_build_params = ""
    for a in new_build_info["actions"]:
        try:
            if a["_class"] == "hudson.model.ParametersAction":
                new_build_params = a["parameters"]
                for param in ignore_paramers:
                    for new_param in new_build_params:
                        if param == new_param["name"]:
                            new_build_params.remove(new_param)
                            break

        except KeyError:
            pass
    logger.debug("New build: {}/{}: {}".format(name, build, new_build_params))

    running_builds = server.get_running_builds()
    print("Number of running builds: {}".format(len(running_builds)))
    for b in running_builds:
        build_info = server.get_build_info(b["name"],b["number"])
        #print("{}: {}".format(b["url"], build_info["actions"]))
        for a in build_info["actions"]:
            try:
                if a["_class"] == "hudson.model.ParametersAction":
                    #print(a["parameters"])
                    for param in ignore_paramers:
                        for new_param in a["parameters"]:
                            if param == new_param["name"]:
                                a["parameters"].remove(new_param)
                                break
                    diffs = DeepDiff(new_build_params, a["parameters"], ignore_order=True,
                                     ignore_string_type_changes=True)
                    if not diffs:
                        #print("Already running: {}".format(b["url"]))
                        return True, "{}/{}".format(b["name"], b["number"])
            except KeyError:
                pass
    return False, None

def get_all_running_job_details(jenkins_server_url):
    connect_to_jenkins(jenkins_server_url)
    running_builds = server.get_running_builds()
    print_builds_detail(running_builds)

def connect_to_jenkins(jenkins_server_url):
    jenkins_url_list = jenkins_server_url.split("/")[0:3]
    jenkins_url = "/".join(jenkins_url_list)
    logger.info("Jenkins url:{}".format(jenkins_url))
    jenkins_host_full = jenkins_url_list[2]
    jenkins_host = jenkins_host_full.split(".")[0]

    helper_config = load_config()
    print(helper_config["jenkins"])

    jenkins_user = helper_config["jenkins"][jenkins_host.upper() + "_JENKINS_USER"]
    jenkins_user_token = helper_config["jenkins"][jenkins_host.upper() + "_JENKINS_TOKEN"]
    logger.info("Jenkins user:{},token:{}".format(jenkins_user, jenkins_user_token))

    global server
    server = connect_jenkins(jenkins_url, jenkins_user, jenkins_user_token)
    return server

def print_builds_detail(builds=None):
    print("Number of builds: {}".format(len(builds)))
    index = 1
    for b in builds:
        build_info = server.get_build_info(b["name"], b["number"])
        # print("{}: {}".format(b["url"], build_info["actions"]))
        results = []
        for a in build_info["actions"]:
            try:
                if a["_class"] == "hudson.model.ParametersAction":
                    # print(a["parameters"])
                    for new_param in a["parameters"]:
                        results.append("{}={}".format(new_param["name"], new_param["value"]))
            except KeyError:
                pass
        print("{}. {}: {}".format(index, b["url"], results))
        index += 1

def check_if_similar_is_job_running(build_url_to_check, ignore_params=None):
    if len(build_url_to_check.split("/"))<6:
        logger.error("URL doesn't contain job name and build!")
        return False, None
    job_name = build_url_to_check.split("/")[-2]
    job_build = int(build_url_to_check.split("/")[-1])
    jenkins_url_list = build_url_to_check.split("/")[0:3]
    jenkins_url = "/".join(jenkins_url_list)
    logger.info("Jenkins url:{}".format(jenkins_url))
    jenkins_host_full = jenkins_url_list[2]
    jenkins_host = jenkins_host_full.split(".")[0]

    helper_config = load_config()
    print(helper_config["jenkins"])

    jenkins_user = helper_config["jenkins"][jenkins_host.upper() + "_JENKINS_USER"]
    jenkins_user_token = helper_config["jenkins"][jenkins_host.upper() + "_JENKINS_TOKEN"]
    logger.info("Jenkins user:{},token:{}".format(jenkins_user, jenkins_user_token))

    ignore_params_list = ["descriptor", "servers", "dispatcher_params", "fresh_run", "rerun_params",
                          "retries", "timeout", "mailing_list", "addPoolServers"]
    if ignore_params:
        new_ignore_params_list = []
        for param in ignore_params.split(","):
            new_ignore_params_list.append(param)
        ignore_params_list = new_ignore_params_list
    logger.info("Skipping parameters: {}".format(ignore_params_list))

    global server
    server = connect_jenkins(jenkins_url, jenkins_user, jenkins_user_token)

    is_running, job_name_build = is_jenkins_job_running(job_name, job_build, ignore_params_list)
    if is_running:
        print("Jenkins build is already running: {}".format(job_name_build))
    else:
        print("No Jenkins build is running similar to: {}/{}".format(job_name, job_build))
    return is_running, job_name_build

def read_config():
    config = configparser.RawConfigParser()
    config.read(CONFIG_FILE)
    #logger.info(config.sections())
    return config

def load_config():
    logger.info("Loading config from {}".format(CONFIG_FILE))
    return read_config()

def parse_arguments():
    parser = OptionParser()
    parser.add_option('-v', '--version', dest='version')
    parser.add_option("-c", "--config", dest="configfile", default=".jenkinshelper.ini",
                        help="Configuration file")
    parser.add_option("-l", "--log-level", dest="loglevel", default="INFO",
                        help="e.g -l info,warning,error")
    parser.add_option("-u", "--url", dest="build_url_to_check",
                      default='http://qa.sc.couchbase.com', help="Build URL to check")
    parser.add_option("-i", "--ignore", dest="ignore_params", help="Igore parameters list")
    parser.add_option("-j", "--is_job_running", dest="is_job_running", action="store_true",
                      help="Check if a job is running")
    parser.add_option("-r", "--get_running_builds", dest="get_running_builds", action="store_true",
                      help="Get running builds")
    parser.add_option("-q", "--get_queued_builds", dest="get_queued_builds", action="store_true",
                      help="Get running builds")
    parser.add_option("-s", "--get_slaves", dest="get_slaves", action="store_true",
                      help="Get slaves")
    options, args = parser.parse_args()

    if options.build_url_to_check:
        build_url_to_check = options.build_url_to_check
    global CONFIG_FILE
    if options.configfile:
        CONFIG_FILE = options.configfile
    if len(args)==1:
        build_url_to_check = args[0]

    if not build_url_to_check:
        logger.error("No jenkins build url given!")
        sys.exit(1)

    logger.info("Given build url={}".format(build_url_to_check))

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


def main():
    options = parse_arguments()
    set_log_level(options.loglevel)
    if options.is_job_running:
        check_if_similar_is_job_running(options.build_url_to_check,
                                                   options.ignore_params)
    if options.get_running_builds:
        get_all_running_job_details(options.build_url_to_check)
    if options.get_queued_builds:
        get_queued_jobs_list(options.build_url_to_check)
    if options.get_slaves:
        get_slave_nodes(options.build_url_to_check)

if __name__ == "__main__":
    main()