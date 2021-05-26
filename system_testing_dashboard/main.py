from couchbase.options import LockMode
from flask import Flask
from flask import render_template, redirect, flash, make_response
import requests
import time
import datetime
import requests_cache
from flask import request
from couchbase.cluster import Cluster, ClusterOptions
from couchbase.auth import PasswordAuthenticator
from uuid import uuid4
from datetime import datetime
import os
import traceback
from configparser import ConfigParser
from requests.auth import HTTPBasicAuth

CB_BUCKET = os.environ.get("CB_BUCKET") or "system_test_dashboard"
CB_USERNAME = os.environ.get("CB_USERNAME") or "Administrator"
CB_PASSWORD = os.environ.get("CB_PASSWORD") or "password"

cluster = Cluster("couchbase://{}".format(os.environ["CB_SERVER"]), ClusterOptions(
    PasswordAuthenticator(CB_USERNAME, CB_PASSWORD), lockmode=LockMode.WAIT))
bucket = cluster.bucket(CB_BUCKET)
collection = bucket.default_collection()

requests_cache.install_cache(expire_after=60, backend="memory")

app = Flask("systen_testing_dashbord")

app.secret_key = b'\xe0\xac#\x06\xe3\xc5\x19\xd6\xfd\xaf+e\xb9\xd0\xb0\x1f'

LAUNCHER_TO_PARSER_CACHE = {}
JENKINS_PREFIX = "http://qa.sc.couchbase.com/job/"


def fetch_launchers():
    global LAUNCHERS
    try:
        LAUNCHERS = bucket.get("launchers").value
    except Exception:
        LAUNCHERS = []


fetch_launchers()


class Reservation:
    def __init__(self, id, reserved_by, purpose, start, end, cluster, cluster_url, eagle_eye_url, live_start_time, live_duration, parameters):
        self.id = id
        self.reserved_by = reserved_by
        self.purpose = purpose
        self.start = start
        self.end = end
        self.cluster = cluster
        self.duration = format_duration(self.end - self.start)
        self.active = start <= time.time() and end >= time.time()
        self.cluster_url = cluster_url
        self.cluster_short_url = self.cluster_url.replace(
            JENKINS_PREFIX, "") if self.cluster_url else ""
        self.eagle_eye_url = eagle_eye_url
        self.eagle_eye_short_url = self.eagle_eye_url.replace(
            JENKINS_PREFIX, "") if self.eagle_eye_url else ""
        self.eagle_eye_build_id = self.eagle_eye_short_url.strip(
            "/").split("/")[-1] if self.eagle_eye_short_url else ""
        self.live_start_time = live_start_time
        self.live_duration = format_duration(
            live_duration/1000) if live_duration else None
        self.parameters = parameters


class Launcher:
    def __init__(self, name, build):
        self.running = build["building"]
        if not self.running:
            self.result = build["result"]
        self.job_name = name
        self.build_num = build["number"]
        self.job_url = build["url"]
        self.short_job_url = build["url"].replace(JENKINS_PREFIX, "")
        self.started = build["timestamp"] / 1000
        try:
            self.started_by = getAction(build["actions"], "causes")[
                0]["userName"]
        except Exception:
            self.started_by = ""
        self.running_for = get_running_for(
            build["timestamp"]) if self.running else ""
        log_parser_build = get_log_parser_build(build["url"])
        self.log_parser = LogParser(
            log_parser_build) if log_parser_build else None
        self.reservations = []
        self.parameters = parameters_to_dict(
            getAction(build["actions"], "parameters"))


class LogParser:
    def __init__(self, build) -> None:
        self.url = build["url"]
        self.short_url = build["url"].replace(JENKINS_PREFIX, "")
        self.result = build["result"]
        self.running = build["building"]
        self.running_for = get_running_for(
            build["timestamp"]) if self.running else ""
        self.build_id = build["number"]


def parameters_to_dict(parameters):
    ret = {}
    for parameter in parameters:
        ret[parameter["name"]] = parameter["value"]
    return ret


def getAction(actions, key, value=None):
    """
    Parse the actions JSON provided by the Jenkins API and return a named field
    """
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
    """
    Scan the console of a launcher job to get the IPs from the ansible output
    """
    ips = set()
    read_ip = False
    timeout = 5
    end = time.time() + timeout
    with requests_cache.disabled():
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
    """
    Search through the latest log parser jobs to find one where the cluster_node parameter matches an ip in ips
    """
    log_parser = None
    job_json = requests.get(
        JENKINS_PREFIX + "system_test_log_parser/api/json").json()
    for build in job_json["builds"]:
        json = requests.get(build["url"] + "api/json").json()
        parameters = getAction(json["actions"], "parameters")
        cluster_node = getAction(parameters, "name", "cluster_node")
        if cluster_node in ips:
            log_parser = json
            break
    return log_parser


def log_parser_from_upstream(upstream):
    """
    Search through the latest log parser jobs to find one where the upstream job matches
    """
    log_parser = None
    job_json = requests.get(
        JENKINS_PREFIX + "system_test_log_parse/api/json").json()
    for build in job_json["builds"]:
        json = requests.get(build["url"] + "api/json").json()
        causes = getAction(json["actions"], "causes")
        upstream_build_id = getAction(causes, "upstreamBuild")
        upstream_project = getAction(causes, "upstreamProject")
        upstream_url = "{}{}/{}/".format(JENKINS_PREFIX,
                                         upstream_project, upstream_build_id)
        if upstream_url == upstream:
            log_parser = json
            break
    return log_parser


def get_log_parser_build(launcher_job_url):
    """
    Get the log parser associated with a launcher
    """
    if launcher_job_url in LAUNCHER_TO_PARSER_CACHE:
        return requests.get(LAUNCHER_TO_PARSER_CACHE[launcher_job_url] + "api/json").json()

    log_parser = log_parser_from_upstream(launcher_job_url)
    if log_parser is None:
        ips = get_launcher_ips(launcher_job_url)
        if ips:
            log_parser = log_parser_from_ips(ips)
    if log_parser:
        LAUNCHER_TO_PARSER_CACHE[launcher_job_url] = log_parser["url"]
        return log_parser

    return None


def get_running_for(started):
    """
    Convert 
    """
    return format_duration(time.time() - started / 1000)


def format_duration(seconds):
    return str(round(seconds / (60 * 60))) + " hrs"


def get_active_reservations():
    current_time = time.time()
    reservations = list(bucket.query(
        "select purpose, reserved_by, `start`, `end`, `cluster`, META().id, cluster_url, eagle_eye_url, live_start_time, live_duration, parameters from {0} where `end` >= {1} order by `start` asc".format(CB_BUCKET, current_time)))
    return [Reservation(reservation["id"], reservation["reserved_by"], reservation["purpose"], reservation["start"], reservation["end"], reservation["cluster"], reservation["cluster_url"], reservation["eagle_eye_url"], reservation["live_start_time"], reservation["live_duration"], reservation["parameters"]) for reservation in reservations]


def get_reservation_history():
    current_time = time.time()
    reservations = list(bucket.query("select purpose, reserved_by, `start`, `end`, `cluster`, META().id, cluster_url, eagle_eye_url, live_start_time, live_duration, parameters from {} where not deleted and `start` < `end` and `end` < {} order by `end` desc".format(CB_BUCKET, current_time)))
    return [Reservation(reservation["id"], reservation["reserved_by"], reservation["purpose"], reservation["start"], reservation["end"], reservation["cluster"], reservation["cluster_url"], reservation["eagle_eye_url"], reservation["live_start_time"], reservation["live_duration"], reservation["parameters"]) for reservation in reservations]


def release_reservation(id):
    current_time = time.time()
    bucket.query("update {} set `end` = {} where META().id = '{}'".format(
        CB_BUCKET, current_time, id)).execute()


def associate_job_with_reservation(launcher, reservation):
    try:
        doc = bucket.get(reservation.id).value
        doc["cluster_url"] = launcher.job_url
        doc["live_start_time"] = launcher.started
        doc["parameters"] = launcher.parameters
        if launcher.log_parser:
            doc["eagle_eye_url"] = launcher.log_parser.url
        collection.upsert(reservation.id, doc)
    except Exception:
        # Try again next time
        pass


def add_cluster_duration_to_reservation(reservation):
    try:
        doc = bucket.get(reservation.id).value
        res = requests.get(reservation.cluster_url + "api/json").json()
        if not res["building"] and res["duration"] > 0:
            doc["live_duration"] = res["duration"]
            collection.upsert(reservation.id, doc)
    except Exception:
        # Try again next time
        pass


def is_install_finished(launcher_job_url):
    timeout = 5
    end = time.time() + timeout
    with requests_cache.disabled():
        for line in requests.get(launcher_job_url + "consoleText", timeout=timeout, stream=True).iter_lines(decode_unicode=True):
            if time.time() > end:
                break
            if line.startswith("+ ./sequoia -client"):
                return True
    return False


def create_launch_history(launchers):
    for launcher in launchers.values():
        if not launcher.running or (launcher.reservations and launcher.reservations[0].active):
            continue
        existing = list(bucket.query(
            "select raw count(*) from {} where cluster_url = '{}'".format(CB_BUCKET, launcher.job_url)))[0] > 0
        if existing:
            continue
        install_finished = is_install_finished(launcher.job_url)
        if not install_finished:
            continue
        doc = {
            "launcher": launcher.job_name,
            "parameters": launcher.parameters,
            "live_start_time": launcher.started,
            "cluster_url": launcher.job_url,
            "eagle_eye_url": launcher.log_parser.url if launcher.log_parser else None,
            "type": "launcher",
            "deleted": False,
            "started_by": launcher.started_by,
            "live_duration": None
        }
        id = "launcher_{}_{}".format(launcher.job_name, launcher.build_num)
        collection.insert(id, doc)


def get_launchers():
    fetch_launchers()
    launchers = {}
    for job_name in LAUNCHERS:
        job_json = requests.get(
            "{}{}/api/json".format(JENKINS_PREFIX, job_name)).json()
        latest_build_json = requests.get(
            job_json["lastBuild"]["url"] + "/api/json").json()
        latest_launcher = Launcher(job_name, latest_build_json)
        launchers[job_name] = latest_launcher
    return launchers


def create_reservation_from_launcher(launcher):
    end = launcher["live_start_time"] + int(launcher["parameters"]["duration"])
    return Reservation(launcher["id"], launcher["started_by"], "", launcher["live_start_time"], end, launcher["launcher"], launcher["cluster_url"], launcher["eagle_eye_url"], launcher["live_start_time"], launcher["live_duration"], launcher["parameters"])


def get_launcher_history():
    launchers = list(bucket.query(
        "select launcher, parameters, live_start_time, cluster_url, eagle_eye_url, started_by, live_duration, META().id from {} where not deleted and `type` = 'launcher'".format(CB_BUCKET)))
    return [create_reservation_from_launcher(launcher) for launcher in launchers]


@app.template_filter("timestamp")
def format_timestamp(timestamp):
    return datetime.fromtimestamp(int(timestamp))


@app.route("/")
def index():
    launchers = get_launchers()
    reservations = get_active_reservations()
    for reservation in reservations:
        launcher = launchers[reservation.cluster]
        if reservation.active and launcher.running and (reservation.cluster_url is None or reservation.eagle_eye_url is None):
            associate_job_with_reservation(launcher, reservation)
        launcher.reservations.append(reservation)

    launcher_history = get_launcher_history()
    create_launch_history(launchers)

    # delete launcher history if now a reservation associated
    for historic_launcher in launcher_history:
        if historic_launcher.end > time.time() and historic_launcher.cluster in launchers:
            launcher = launchers[historic_launcher.cluster]
            for reservation in launcher.reservations:
                if reservation.active and reservation.cluster_url == historic_launcher.cluster_url:
                    collection.remove(historic_launcher.id)

    reservation_history = get_reservation_history()
    reservation_history.extend(launcher_history)
    reservation_history.sort(key=lambda r: r.end, reverse=True)
    for reservation in reservation_history:
        if reservation.cluster_url and reservation.live_duration is None:
            add_cluster_duration_to_reservation(reservation)

    return render_template('index.html', launchers=list(launchers.values()), reservation_history=reservation_history, server_time=time.time())


@app.route("/release/<string:id>")
def release(id):
    try:
        release_reservation(id)
    except Exception as e:
        flash("Couldn't release reservation: {}".format(e))
    return redirect("/")


@app.route("/reserve", methods=["POST"])
def reserve():
    try:
        user = request.form['name']
        if user == "":
            raise ValueError("Name must not be empty")
        cluster = request.form['cluster']
        if cluster not in LAUNCHERS:
            raise ValueError("Invalid cluster")
        duration = float(request.form['duration'])
        if duration <= 0:
            raise ValueError("Duration must must > 0")
        purpose = request.form['purpose']
        if purpose == "":
            raise ValueError("Purpose must not be empty")
        start_date = request.form["startDate"]
        start_time = request.form["startTime"]
        start = time.time()
        custom_start = start_date
        if custom_start != "":
            if start_time == "":
                custom_start += " 00:00"
            else:
                custom_start += " " + start_time
            start = datetime.strptime(
                custom_start, "%Y-%m-%d %H:%M").timestamp()
        end = start + (duration * 60 * 60)
        id = str(uuid4())

        # overlaps if start or end is within another reservation or start is before and end is after another reservation
        overlap = "(({0} >= `start` and {0} <= `end`) or ({1} >= `start` and {1} <= `end`) or ({0} < `start` and {1} > `end`))".format(
            start, end)
        existing_reservations = list(bucket.query(
            "select raw count(*) from {} where `start` < `end` and {} and `cluster` = '{}'".format(CB_BUCKET, overlap, cluster)))[0] > 0
        if existing_reservations:
            raise Exception("Existing reservation")

        doc = {
            "start": start,
            "end": end,
            "cluster": cluster,
            "purpose": purpose,
            "reserved_by": user,
            "cluster_url": None,
            "eagle_eye_url": None,
            "live_start_time": None,
            "live_duration": None,
            "parameters": None,
            "deleted": False
        }

        collection.insert(id, doc)
    except Exception as e:
        flash("Couldn't reserve cluster: {}".format(e))
        traceback.print_exc()
    return redirect("/")


@app.route("/deleteHistory/<string:id>")
def delete_history(id):
    bucket.query("update {} set deleted = true where META().id = '{}'".format(
        CB_BUCKET, id)).execute()
    return redirect("/")


credentials = ConfigParser()
credentials.read("credentials.ini")


def get_auth(server):
    auth = None
    for url in credentials.sections():
        if server.startswith(url):
            try:
                username = credentials.get(url, "username")
                password = credentials.get(url, "password")
            except ConfigParser.NoOptionError:
                pass
            else:
                auth = HTTPBasicAuth(username, password)
                break
    return auth


@app.route("/stop/<string:job_name>")
def stop(job_name):
    if job_name not in LAUNCHERS:
        raise Exception("Unknown launcher")
    job_json = requests.get(
        "{}{}/api/json".format(JENKINS_PREFIX, job_name)).json()
    build_id = job_json["lastBuild"]["number"]
    launcher_job_url = "{}{}/{}/".format(JENKINS_PREFIX, job_name, build_id)
    log_parser_job = get_log_parser_build(launcher_job_url)
    if log_parser_job is not None:
        log_parser_stop_url = log_parser_job["url"] + "stop"
        auth = get_auth(log_parser_stop_url)
        requests.post(log_parser_stop_url, auth=auth)
    launcher_stop_url = launcher_job_url + "stop"
    auth = get_auth(launcher_stop_url)
    requests.post(launcher_stop_url, auth=auth)
    return redirect("/")


@app.route("/log_parser_results/<int:build_id>")
def log_parser(build_id):
    log_parser_results = bucket.get(
        "log_parser_results_{}".format(build_id), quiet=True)
    if log_parser_results.value is None:
        response = "No results found"
    else:
        response = "\n".join(log_parser_results.value)
    response = make_response(response, 200)
    response.mimetype = "text/plain"
    return response


app.run("0.0.0.0", 8080, debug=True)
