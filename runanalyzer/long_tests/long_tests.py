from datetime import timedelta
from typing import Any, List, Tuple
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster, ClusterOptions, ClusterTimeoutOptions
import sys
import requests
from multiprocessing import Pool
import traceback
import os

CB_BUILD = sys.argv[1]
CB_USER = os.environ["CB_USER"]
CB_PASSWORD = os.environ["CB_PASSWORD"]



cluster = Cluster("couchbase://172.23.121.84", ClusterOptions(PasswordAuthenticator("Administrator", "password"),timeout_options=ClusterTimeoutOptions(kv_timeout=timedelta(seconds=10))))
bucket = cluster.bucket("greenboard")
doc = bucket.get("{}_server".format(CB_BUILD)).value

def filter_fields(testname):
    # TODO: Fix for old xml style
    if "logs_folder:" in testname:
        testwords = testname.split(",")
        line = ""
        for fw in testwords:
            if not fw.startswith("logs_folder") and not fw.startswith("conf_file") \
                    and not fw.startswith("cluster_name:") \
                    and not fw.startswith("ini:") \
                    and not fw.startswith("case_number:") \
                    and not fw.startswith("num_nodes:") \
                    and not fw.startswith("spec:"):
                if not "\":" in fw or "query:" in fw:
                    #log.info("Replacing : with ={}".format(fw))
                    line = line + fw.replace(":", "=", 1)
                else:
                    line = line + fw
                if fw != testwords[-1]:
                    line = line + ","

        return line    
    else:
        testwords = testname.split(",")
        line = []
        for fw in testwords:
            if not fw.startswith("logs_folder=") and not fw.startswith("conf_file=") \
                    and not fw.startswith("cluster_name=") \
                    and not fw.startswith("ini=") \
                    and not fw.startswith("case_number=") \
                    and not fw.startswith("num_nodes=") \
                    and not fw.startswith("spec="):
                line.append(fw)
        return ",".join(line)

def get_test_report(run):
    executor = run["url"].split('/')[-2]
    test_report_url = "http://cb-logs-qe.s3-website-us-west-2.amazonaws.com/" + cb_build + "/jenkins_logs/" + executor + "/"+ str(run["build_id"]) + "/testresult.json"
    tr = requests.get(test_report_url).json()
    for suite in tr["suites"]:
        for case in suite["cases"]:
            case["name"] = filter_fields(case["name"])
    return tr

def get_test(name, report):
    for suite in report["suites"]:
        for case in suite["cases"]:
            if case["name"] == name:
                return case
    return None

def find_exceptions(job_name, fresh_run, best_run):
    try:
        if best_run["failCount"] == fresh_run["failCount"]:
            return
        fresh_test_report, best_test_report = get_test_report(fresh_run), get_test_report(best_run)
        for suite in best_test_report["suites"]:
            for case in suite["cases"]:
                fresh_test = get_test(case["name"], fresh_test_report)
                if case["status"] == "PASSED" and fresh_test["status"] == "FAILED" and "ImportError" not in fresh_test["errorStackTrace"]:
                    print(job_name + " " + case["name"])
                    print(fresh_test["errorStackTrace"] + "\n")
    except Exception:
        pass

if __name__ == "__main__":
    with Pool(10) as pool:
        all_runs = []
        for component in doc["os"]["CENTOS"]:
            for job_name in doc["os"]["CENTOS"][component]:
                runs = doc["os"]["CENTOS"][component][job_name]
                best_run = next(filter(lambda run: run["olderBuild"] == False, runs), None)
                fresh_run = runs[-1]
                if best_run and best_run["build_id"] != runs[-1]["build_id"]:
                    all_runs.append((job_name, fresh_run, best_run,))
        pool.starmap(find_exceptions, all_runs)
        pool.close()
        pool.join()
