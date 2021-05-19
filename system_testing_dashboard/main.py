from couchbase.options import LockMode
from flask import Flask
from flask import render_template, redirect, flash
import requests
import time
import datetime
import requests_cache
from flask import request
from couchbase.cluster import Cluster, ClusterOptions
from couchbase.auth import PasswordAuthenticator
from uuid import uuid4
from datetime import datetime, timedelta
import os
import traceback

CB_BUCKET = os.environ.get("CB_BUCKET") or "system_test_dashboard"
CB_USERNAME = os.environ.get("CB_USERNAME") or "Administrator"
CB_PASSWORD = os.environ.get("CB_PASSWORD") or "password"

cluster = Cluster("couchbase://{}".format(os.environ["CB_SERVER"]), ClusterOptions(PasswordAuthenticator(CB_USERNAME, CB_PASSWORD), lockmode=LockMode.WAIT))
bucket = cluster.bucket(CB_BUCKET)
collection = bucket.default_collection()

requests_cache.install_cache(expire_after=60, backend="memory")

app = Flask("systen_testing_dashbord")

app.secret_key = b'\xe0\xac#\x06\xe3\xc5\x19\xd6\xfd\xaf+e\xb9\xd0\xb0\x1f'

NUM_LAUNCHERS = 4
LAUNCHER_TO_PARSER_CACHE = {}
JENKINS_PREFIX = "http://qa.sc.couchbase.com/job/"

class Reservation:
    def __init__(self, id, reserved_by, purpose, start, end, cluster, cluster_url, eagle_eye_url, live_start_time, live_duration):
        self.id = id
        self.reserved_by = reserved_by
        self.purpose = purpose
        self.start = start
        self.end = end
        self.cluster = cluster
        self.duration = str(timedelta(seconds=self.end - self.start)).split(".")[0]
        self.active = start <= time.time() and end >= time.time()
        self.cluster_url = cluster_url
        self.cluster_short_url = self.cluster_url.replace(JENKINS_PREFIX, "") if self.cluster_url else ""
        self.eagle_eye_url = eagle_eye_url
        self.eagle_eye_short_url = self.eagle_eye_url.replace(JENKINS_PREFIX, "") if self.eagle_eye_url else ""
        self.live_start_time = live_start_time
        self.live_duration = str(timedelta(seconds=live_duration/1000)).split(".")[0] if live_duration else None

class Launcher:
    def __init__(self, number, name, build):
        self.number = number
        self.running = build["building"]
        if not self.running:
            self.result = build["result"]
        self.job_name = name
        self.build_num = build["number"]
        self.job_url = build["url"]
        self.short_job_url = build["url"].replace(JENKINS_PREFIX, "")
        self.started = build["timestamp"] / 1000
        self.running_for = get_running_for(build["timestamp"]) if self.running else ""
        log_parser_build = get_log_parser_build(build["url"])
        self.log_parser = LogParser(log_parser_build) if log_parser_build else None
        self.reservations = []

class LogParser:
    def __init__(self, build) -> None:
        self.url = build["url"]
        self.short_url = build["url"].replace(JENKINS_PREFIX, "")
        self.result = build["result"]
        self.running = build["building"]
        self.running_for = get_running_for(build["timestamp"]) if self.running else ""


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
    job_json = requests.get(JENKINS_PREFIX + "system_test_log_parser/api/json").json()
    for build in job_json["builds"]:
        json = requests.get(build["url"] + "api/json").json()
        parameters = getAction(json["actions"], "parameters")
        cluster_node = getAction(parameters, "name", "cluster_node")
        if cluster_node in ips:
            log_parser = json
            break
    return log_parser


def get_log_parser_build(launcher_job_url):
    """
    Get the log parser associated with a launcher
    """
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
    """
    Convert 
    """
    return str(timedelta(seconds=time.time() - started / 1000)).split(".")[0]


def get_active_reservations():
    current_time = time.time()
    reservations = list(bucket.query("select purpose, reserved_by, `start`, `end`, `cluster`, META().id, cluster_url, eagle_eye_url, live_start_time, live_duration from {0} where `end` >= {1} order by `start` asc".format(CB_BUCKET, current_time)))
    return [Reservation(reservation["id"], reservation["reserved_by"], reservation["purpose"], reservation["start"], reservation["end"], reservation["cluster"], reservation["cluster_url"], reservation["eagle_eye_url"], reservation["live_start_time"], reservation["live_duration"]) for reservation in reservations]


def get_reservation_history():
    current_time = time.time()
    reservations = list(bucket.query("select purpose, reserved_by, `start`, `end`, `cluster`, META().id, cluster_url, eagle_eye_url, live_start_time, live_duration from {} where `start` < `end` and `end` < {} order by `end` desc".format(CB_BUCKET, current_time)))
    return [Reservation(reservation["id"], reservation["reserved_by"], reservation["purpose"], reservation["start"], reservation["end"], reservation["cluster"], reservation["cluster_url"], reservation["eagle_eye_url"], reservation["live_start_time"], reservation["live_duration"]) for reservation in reservations]


def release_reservation(id):
    current_time = time.time()
    bucket.query("update {} set `end` = {} where META().id = '{}'".format(CB_BUCKET, current_time, id)).execute()


def associate_job_with_reservation(launcher, reservation):
    try:
        doc = bucket.get(reservation.id).value
        doc["cluster_url"] = launcher.job_url
        doc["live_start_time"] = launcher.started
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


def get_launchers():
    launchers = []
    for i in range(1, NUM_LAUNCHERS + 1):
        job_name = "component_systest_launcher"
        if i > 1:
            job_name += "_" + str(i)
        job_json = requests.get("http://qa.sc.couchbase.com/job/{}/api/json".format(job_name)).json()
        latest_build_json = requests.get(job_json["lastBuild"]["url"] + "/api/json").json()
        latest_launcher = Launcher(i, job_name, latest_build_json)
        launchers.append(latest_launcher)
    return launchers


@app.template_filter("timestamp")
def format_timestamp(timestamp):
    return datetime.fromtimestamp(int(timestamp))


@app.route("/")
def index():
    launchers = get_launchers()
    reservations = get_active_reservations()
    for reservation in reservations:
        launcher = launchers[reservation.cluster - 1]
        if reservation.active and launcher.running and reservation.cluster_url is None:
            reservation.cluster_url = launcher.job_url
            associate_job_with_reservation(launcher, reservation)
        launchers[reservation.cluster - 1].reservations.append(reservation)
    reservation_history = get_reservation_history()
    for reservation in reservation_history:
        if reservation.cluster_url and reservation.live_duration is None:
            add_cluster_duration_to_reservation(reservation)

    return render_template('index.html', launchers=launchers, reservation_history=reservation_history, server_time=time.time())


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
        cluster = int(request.form['cluster'])
        if cluster not in range(1, NUM_LAUNCHERS + 1):
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
            start = datetime.strptime(custom_start, "%Y-%m-%d %H:%M").timestamp()
        end = start + (duration * 60 * 60)
        id = str(uuid4())

        # overlaps if start or end is within another reservation or start is before and end is after another reservation
        overlap = "(({0} >= `start` and {0} <= `end`) or ({1} >= `start` and {1} <= `end`) or ({0} < `start` and {1} > `end`))".format(start, end)
        existing_reservations = list(bucket.query("select raw count(*) from {} where `start` < `end` and {} and `cluster` = {}".format(CB_BUCKET, overlap, cluster)))[0] > 0
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
            "live_duration": None
        }

        collection.insert(id, doc)
    except Exception as e:
        flash("Couldn't reserve cluster: {}".format(e))
        traceback.print_exc()
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


@app.route("/stop/<int:launcher>")
def stop(launcher):
    if launcher < 1 or launcher > NUM_LAUNCHERS:
        raise Exception("Unknown launcher")
    job_name = launcher_name(launcher)
    job_json = requests.get("{}{}/api/json".format(JENKINS_PREFIX, job_name)).json()
    build_id = job_json["lastBuild"]["number"]
    url = "{}{}/{}/stop".format(JENKINS_PREFIX, job_name, build_id)
    # TODO: Get downstream log parser and abort
    auth = get_auth(url)
    print(url)
    # requests.post(url, auth=auth)
    return redirect("/")


app.run("0.0.0.0", 8080, debug=True)