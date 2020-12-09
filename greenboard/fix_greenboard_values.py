from couchbase.cluster import Cluster, ClusterOptions
from couchbase.auth import PasswordAuthenticator
import traceback
from couchbase.collection import ReplaceOptions
from couchbase.exceptions import CASMismatchException, DocumentExistsException

import requests

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

# Very expsive API call (5+ seconds)
response = requests.get("http://qa.sc.couchbase.com/api/json?tree=jobs[name,builds[number,actions[parameters[name,value]]]]&pretty=true").json()

versions = set()

for job in response["jobs"]:
    for build in job["builds"]:
        try:
            parameters = getAction(build["actions"], "parameters")
            if parameters:
                version = getAction(parameters, "name", "version_number")
                if version:
                    versions.add(version)
        except KeyError:
            pass

cluster = Cluster("couchbase://172.23.121.84", ClusterOptions(
    PasswordAuthenticator("Administrator", "password")))

print("connected")

server_bucket = cluster.bucket("server")
greenboard_bucket = cluster.bucket("greenboard")
greenboard_collection = greenboard_bucket.default_collection()

for version in versions:
    try:
        while True:
            # Make generic?
            doc_id = "{}_server".format(version)

            doc = greenboard_collection.get(doc_id)
            cas = doc.cas
            greenboard = doc.content_as[dict]["os"]

            for row in server_bucket.query("select build_id, os, component, name, totalCount, failCount, result from server where `build` = '{}'".format(version)):
                try:
                    all_runs = greenboard[row["os"]][row["component"]][row["name"]]

                    keys_to_check = ["color", "duration", "failCount", "result", "totalCount"]

                    for run in all_runs:
                        if row["build_id"] == run["build_id"]:

                            for key in keys_to_check:
                                if key in row and key in run and row[key] != run[key]:
                                    run[key] = row[key]
                                    print("corrected {} for {} in {}".format(key, row["name"], version))

                except Exception:
                    traceback.print_exc()
                    continue

            break

            # try:
            #     greenboard_collection.replace(doc_id, greenboard, ReplaceOptions(cas=cas))
            #     break
            # except (CASMismatchException, DocumentExistsException):
            #     continue

            
    except Exception:
        traceback.print_exc()