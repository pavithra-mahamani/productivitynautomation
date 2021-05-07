from flask import Flask
from flask import render_template
import requests
import time
import datetime

app = Flask("systen_testing_dashbord")

NUM_LAUNCHERS = 4
LAUNCHER_TO_PARSER_CACHE = {}

class Launcher:
    running = False
    result = ""
    build_num = 0
    job_name = ""
    number = 0
    job_url = ""
    log_parser = None
    user = ""
    running_for = ""
    started = 0

    def __init__(self, number, name, build):
        self.number = number
        self.running = build["building"]
        if not self.running:
            self.result = build["result"]
        self.job_name = name
        self.build_num = build["number"]
        self.job_url = build["url"]
        self.user = getAction(build["actions"], "causes")[0]["userName"]
        self.started = build["timestamp"]
        if self.running:
            self.running_for = get_running_for(build["timestamp"])
        log_parser_build = get_log_parser_build(build["url"])
        if log_parser_build:
            self.log_parser = LogParser(log_parser_build)

class LogParser:
    running = False
    result = ""
    url = ""
    running_for = ""

    def __init__(self, build) -> None:
        self.url = build["url"]
        self.result = build["result"]
        self.running = build["building"]
        if self.running:
            self.running_for = get_running_for(build["timestamp"])

def getAction(actions, key, value=None):
    if actions is None:
        return None

    obj = None
    keys = []
    for a in actions:
        if a is None:
            continue
        if 'keys' in dir(a):
            keys = a.keys()
        else:
            # check if new api
            if 'keys' in dir(a[0]):
                keys = a[0].keys()
        if "urlName" in keys:
            if a["urlName"] != "robot" and a["urlName"] != "testReport" and a["urlName"] != "tapTestReport":
                continue

        if key in keys:
            if value:
                if a["name"] == value:
                    obj = a["value"]
                    break
            else:
                obj = a[key]
                break

    return obj


def get_launcher_ips(launcher_job_url):
    ips = set()
    read_ip = False
    timeout = 5
    end = time.time() + timeout
    for line in requests.get(launcher_job_url + "consoleText", timeout=timeout, stream=True).iter_lines(decode_unicode=True):
        if time.time() > end:
            break
        if read_ip:
            if line.startswith("ok: ["):
                ips.add(line.replace("ok: [", "").replace("]", ""))
            else:
                break
        elif "TASK [Gathering Facts]" in line:
            read_ip = True
    return ips

def log_parser_from_ips(ips):
    log_parser = None
    job_json = requests.get("http://qa.sc.couchbase.com/job/system_test_log_parser/api/json").json()
    for build in job_json["builds"]:
        json = requests.get(build["url"] + "api/json").json()
        parameters = getAction(json["actions"], "parameters")
        cluster_node = getAction(parameters, "name", "cluster_node")
        if cluster_node in ips:
            log_parser = json
            break
    return log_parser

def get_log_parser_build(launcher_job_url):
    if launcher_job_url in LAUNCHER_TO_PARSER_CACHE:
        return requests.get(LAUNCHER_TO_PARSER_CACHE[launcher_job_url] + "api/json").json()

    ips = get_launcher_ips(launcher_job_url)
    if ips:
        log_parser = log_parser_from_ips(ips)
        if log_parser:
            LAUNCHER_TO_PARSER_CACHE[launcher_job_url] = log_parser["url"]
        return log_parser

    return None

def get_running_for(started):
    return str(datetime.timedelta(seconds=time.time() - started / 1000)).split(".")[0]


@app.route("/")
def index():
    launchers = []
    history = []
    for i in range(1, NUM_LAUNCHERS + 1):
        job_name = "component_systest_launcher"
        if i > 1:
            job_name += "_" + str(i)
        job_json = requests.get("http://qa.sc.couchbase.com/job/{}/api/json".format(job_name)).json()
        latest_build_json = requests.get(job_json["lastBuild"]["url"] + "/api/json").json()
        launchers.append(Launcher(i, job_name, latest_build_json))

        for build in job_json["builds"][1:]:
            build_json = requests.get(build["url"] + "/api/json").json()
            history.append(Launcher(i, job_name, build_json))

    history.sort(key=lambda launcher: launcher.started, reverse=True)

    return render_template('index.html', launchers=launchers, history=history)

app.run("0.0.0.0", 8080, debug=True)