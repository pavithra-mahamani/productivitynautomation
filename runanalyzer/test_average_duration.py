from couchbase.cluster import Cluster, ClusterOptions, PasswordAuthenticator
from typing import Dict, List, TypedDict
from multiprocessing import Pool
import requests
import statistics
import csv
import os

CB_USERNAME = os.environ["CB_USERNAME"]
CB_PASSWORD = os.environ["CB_PASSWORD"]

cluster = Cluster("couchbase://172.23.121.84", ClusterOptions(PasswordAuthenticator(CB_USERNAME, CB_PASSWORD)))
BUILDS = cluster.query("select raw s.`build` from (SELECT `build`, count(*) c FROM server where `build` like '7.0%' group by `build` order by `build` desc) s where c > 500 limit 8").rows()
FIELD_NAMES = ["result", "job_name", "case", "min", "max", "average", "range", "standard_deviation"] + BUILDS

class Job(TypedDict):
    name: str
    url: str
    build_id: int
    build: str

class TestCase(TypedDict):
    duration: float
    name: str
    status: str

class TestSuite(TypedDict):
    cases: List[TestCase]

class TestReport(TypedDict):
    suites: List[TestSuite]

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

class Case(TypedDict):
    duration: float
    build: str

Cases = Dict[str, Dict[str, List[Case]]]


def write_row(job_name: str, cases: Cases):

    with open('test_cases.csv', 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELD_NAMES)
        for name, results in cases.items():
            for result, durations_by_build in results.items():
                if len(durations_by_build) > 1:
                    durations = [duration_by_build["duration"] for duration_by_build in durations_by_build]
                    minimum = min(durations)
                    maximum = max(durations)
                    average = sum(durations) / len(durations)
                    standard_deviation = statistics.stdev(durations) if len(durations) > 1 else 0
                    range = maximum - minimum
                    row = {
                        "result": result,
                        "job_name": job_name,
                        "case": name,
                        "min": minimum,
                        "max": maximum,
                        "average": average,
                        "range": range,
                        "standard_deviation": standard_deviation
                    }
                    for duration_by_build in durations_by_build:
                        row[duration_by_build["build"]] = duration_by_build["duration"]
                    writer.writerow(row)



def print_average_duration(job: Job):

    cases: Cases  = {}

    try:
        jobs: List[Job] = cluster.query(f"select name, build_id, url, `build` from server where name = '{job['name']}' and `build` in {BUILDS} order by `build` desc limit 8").rows()
    except Exception:
        return
    for job in jobs:
        executor = job["url"].replace("http://qa.sc.couchbase.com/job/", "").strip("/")
        url = f"http://cb-logs-qe.s3-website-us-west-2.amazonaws.com/{job['build']}/jenkins_logs/{executor}/{job['build_id']}/testresult.json"
        try:
            test_report: TestReport = requests.get(url).json()
        except Exception:
            continue
        for suite in test_report["suites"]:
            for case in suite["cases"]:
                case["name"] = filter_fields(case["name"])
                if case["name"] in cases:
                    if case["status"] in cases[case["name"]]:
                        cases[case["name"]][case["status"]].append({ "duration": case["duration"], "build": job["build"] })
                else:
                    cases[case["name"]] = { case["status"]: [{ "duration": case["duration"], "build": job["build"] }] }

    write_row(job["name"], cases)
                

if __name__ == "__main__":
    with open('test_cases.csv', 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELD_NAMES)
        writer.writeheader()

    jobs: List[Job] = cluster.query(f"select name, build_id, url, `build` from server where `build` = '{BUILDS[0]}' and url like '%test_suite_executor%'").rows()

    with Pool(20) as pool:
        pool.map(print_average_duration, jobs)
