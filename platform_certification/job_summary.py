import requests
import tabulate
from requests.auth import HTTPBasicAuth
import argparse
import re

def run_query(query, host="172.23.99.54", port=8093, username="Administrator", password="password", param=None):
    url_base = f"http://{host}:{port}/query/service"
    params = {'statement': query}
    if param:
        params.update(param)
    response = requests.get(url=url_base, params=params, auth = HTTPBasicAuth(username, password))
    return response.json()

def display_table(dataset, fmt="line"):
    header = dataset[0].keys()
    rows =  [x.values() for x in dataset]
    print (tabulate.tabulate(rows, header, tablefmt=fmt))

def process_jenkins_job(job):
    stacks = []
    fail = 0
    for info in job['info']:
        response = requests.get(info['joburl'] + "/testReport/api/json?pretty=true")
        for suite in response.json()['suites']:
            for case in suite['cases']:
                if case['status'] == "FAILED":
                    fail += 1
                    # print (f"Test Case: {case['className']}")
                    stack = re.sub('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', "1.1.1.1", case['errorStackTrace'])
                    stack = re.sub('\d{1,6} bytes read', '9999 bytes read', stack)
                    stack = re.sub('\d{1,6} more expected', '9999 bytes read', stack)
                    if stack not in stacks:
                        stacks.append(stack)
    print(f"Job {job['job']} had {fail} failed test cases on {len(job['info'])} platforms with {len(stacks)} unique stacks")
    for platform in job['info']:
        print(f" - {platform['failures']} failures on {platform['platform']} platform, see details at {platform['joburl']}")  

def parse_args():
    parser = argparse.ArgumentParser(description='Generate platform certification summary')
    parser.add_argument("--release", "-r", default='7.0.0', help="Release number. Default to 7.0.0", type=str)
    parser.add_argument("--build", "-b", default=4342, help="Build number. Default to 4342.", type=int)
    parser.add_argument("--previous", "-p", default=4291, help="Previous Build number. Default to 4291.", type=int)
    parser.add_argument("--table", "-t", default='line', help="Table format can be line or grid. Default to line.", type=str)
    parser.add_argument("--job", "-j", default='', help="List of job name to display and process. Default to all jobs.", type=str)
    parser.add_argument("--status", "-s", default='ABORTED', help="List of job status to show instead of pass/total. Default to ABORTED jobs.", type=str)
    options = parser.parse_args()
    return options

def job_summary(release, current_build, status_list, job_list, table):
    if job_list != ['']:
        query_summary = f'SELECT a.job AS `0_job`, MAX(CASE WHEN a.platform = "centos8" THEN a.result END) AS `1_centos8`, MAX(CASE WHEN a.platform = "centosnonroot" THEN a.result END) AS `2_centosnonroot`, MAX(CASE WHEN a.platform = "debian10" THEN a.result END) AS `3_debian10`, MAX(CASE WHEN a.platform = "ubuntu20" THEN a.result END) AS `4_ubuntu20`, MAX(CASE WHEN a.platform = "suse15" THEN a.result END) AS `5_suse15`, MAX(CASE WHEN a.platform = "oel8" THEN a.result END) AS `6_oel8`, MAX(CASE WHEN a.platform = "windows" THEN a.result END) AS `7_windows`, MAX(CASE WHEN a.platform = "ipv6" THEN a.result END) AS `8_ipv6`, MAX(CASE WHEN a.platform = "centos" THEN a.result END) AS `9_ce` FROM ( SELECT CASE WHEN name LIKE "centos-ipv6%" THEN "ipv6" ELSE SPLIT(name,"-")[0] END AS platform, CASE WHEN name LIKE "centos-ipv6%" THEN REPLACE(SUBSTR(name, LENGTH(SPLIT(name,"-")[0])+6), "ce_", "") ELSE REPLACE(SUBSTR(name, LENGTH(SPLIT(name,"-")[0])+12), "ce_", "") END AS job, CASE WHEN result in {status_list} THEN result ELSE TO_STRING(totalCount-failCount) || "/" || TO_STRING(totalCount) END AS result FROM server WHERE `build`=$version AND (name LIKE "%os_certify%" OR (name LIKE "centos-ipv6%" AND name NOT LIKE "centos-ipv6_sanity%"))) AS a WHERE a.job in {job_list} GROUP BY job ORDER BY job'
    else:
        query_summary = f'SELECT a.job AS `0_job`, MAX(CASE WHEN a.platform = "centos8" THEN a.result END) AS `1_centos8`, MAX(CASE WHEN a.platform = "centosnonroot" THEN a.result END) AS `2_centosnonroot`, MAX(CASE WHEN a.platform = "debian10" THEN a.result END) AS `3_debian10`, MAX(CASE WHEN a.platform = "ubuntu20" THEN a.result END) AS `4_ubuntu20`, MAX(CASE WHEN a.platform = "suse15" THEN a.result END) AS `5_suse15`, MAX(CASE WHEN a.platform = "oel8" THEN a.result END) AS `6_oel8`, MAX(CASE WHEN a.platform = "windows" THEN a.result END) AS `7_windows`, MAX(CASE WHEN a.platform = "ipv6" THEN a.result END) AS `8_ipv6`, MAX(CASE WHEN a.platform = "centos" THEN a.result END) AS `9_ce` FROM ( SELECT CASE WHEN name LIKE "centos-ipv6%" THEN "ipv6" ELSE SPLIT(name,"-")[0] END AS platform, CASE WHEN name LIKE "centos-ipv6%" THEN REPLACE(SUBSTR(name, LENGTH(SPLIT(name,"-")[0])+6), "ce_", "") ELSE REPLACE(SUBSTR(name, LENGTH(SPLIT(name,"-")[0])+12), "ce_", "") END AS job, CASE WHEN result in {status_list} THEN result ELSE TO_STRING(totalCount-failCount) || "/" || TO_STRING(totalCount) END AS result FROM server WHERE `build`=$version AND (name LIKE "%os_certify%" OR (name LIKE "centos-ipv6%" AND name NOT LIKE "centos-ipv6_sanity%"))) AS a WHERE a.job not in ["analytics_rest","obj-ipv6","ent-backup-restore"] GROUP BY job ORDER BY job'
    result = run_query(query=query_summary, param={'$version': f'"{release}-{current_build}"'})
    data = result['results']
    display_table(data, fmt=table)
    print()

def compare_build(release, current_build, last_build, job_list, table):
    if job_list != ['']:
        return
    query_pct = 'SELECT a.`build` as `0_build`, ROUND((SUM(CASE WHEN a.platform = "centos8" THEN a.totalCount END)-SUM(CASE WHEN a.platform = "centos8" THEN a.failCount END))/SUM(CASE WHEN a.platform = "centos8" THEN a.totalCount END)*100,0) AS `1_centos8`, ROUND((SUM(CASE WHEN a.platform = "centosnonroot" THEN a.totalCount END)-SUM(CASE WHEN a.platform = "centosnonroot" THEN a.failCount END))/SUM(CASE WHEN a.platform = "centosnonroot" THEN a.totalCount END)*100,0) AS `2_centosnonroot`, ROUND((SUM(CASE WHEN a.platform = "debian10" THEN a.totalCount END)-SUM(CASE WHEN a.platform = "debian10" THEN a.failCount END))/SUM(CASE WHEN a.platform = "debian10" THEN a.totalCount END)*100,0) AS `3_debian10`, ROUND((SUM(CASE WHEN a.platform = "ubuntu20" THEN a.totalCount END)-SUM(CASE WHEN a.platform = "ubuntu20" THEN a.failCount END))/SUM(CASE WHEN a.platform = "ubuntu20" THEN a.totalCount END)*100,0) AS `4_ubuntu20`, ROUND((SUM(CASE WHEN a.platform = "suse15" THEN a.totalCount END)-SUM(CASE WHEN a.platform = "suse15" THEN a.failCount END))/SUM(CASE WHEN a.platform = "suse15" THEN a.totalCount END)*100,0) AS `5_suse15`, ROUND((SUM(CASE WHEN a.platform = "oel8" THEN a.totalCount END)-SUM(CASE WHEN a.platform = "oel8" THEN a.failCount END))/SUM(CASE WHEN a.platform = "oel8" THEN a.totalCount END)*100,0) AS `6_oel8`, ROUND((SUM(CASE WHEN a.platform = "windows" THEN a.totalCount END)-SUM(CASE WHEN a.platform = "windows" THEN a.failCount END))/SUM(CASE WHEN a.platform = "windows" THEN a.totalCount END)*100,0) AS `7_windows`, ROUND((SUM(CASE WHEN a.platform = "ipv6" THEN a.totalCount END)-SUM(CASE WHEN a.platform = "ipv6" THEN a.failCount END))/SUM(CASE WHEN a.platform = "ipv6" THEN a.totalCount END)*100,0) AS `8_ipv6`, ROUND((SUM(CASE WHEN a.platform = "centos" THEN a.totalCount END)-SUM(CASE WHEN a.platform = "centos" THEN a.failCount END))/SUM(CASE WHEN a.platform = "centos" THEN a.totalCount END)*100,0) AS `9_ce` FROM ( SELECT `build`, name, totalCount, failCount, CASE WHEN name LIKE "centos-ipv6%" THEN "ipv6" ELSE SPLIT(name,"-")[0] END AS platform FROM server WHERE `build` in $version AND (name LIKE "%os_certify%" OR (name LIKE "centos-ipv6%" AND name NOT LIKE "centos-ipv6_sanity%"))) AS a GROUP BY `build` ORDER BY `build` DESC'
    result = run_query(query=query_pct, param={'$version': f'["{release}-{current_build}","{release}-{last_build}"]'})
    data = result['results']
    display_table(data, fmt=table)
    print()

def failure_summary(release, current_build, job_list):
    if job_list == ['']:
        return
    query_job = f'SELECT a.`job`, ARRAY_AGG({{a.`joburl`, a.`platform`, a.`failures`}}) as info FROM ( SELECT CASE WHEN name LIKE "centos-ipv6%" THEN "ipv6" ELSE SPLIT(name,"-")[0] END AS `platform`, CASE WHEN name LIKE "centos-ipv6%" THEN REPLACE(SUBSTR(name, LENGTH(SPLIT(name,"-")[0])+6), "ce_", "") ELSE REPLACE(SUBSTR(name, LENGTH(SPLIT(name,"-")[0])+12), "ce_", "") END AS `job`, failCount as `failures`, url || to_string(build_id) as `joburl` FROM server WHERE `build`=$version AND (name LIKE "%os_certify%" OR (name LIKE "centos-ipv6%" AND name NOT LIKE "centos-ipv6_sanity%")) AND result = "UNSTABLE" ORDER by `job`, `platform`) as a  WHERE a.job IN {job_list} GROUP BY a.`job`'
    result = run_query(query=query_job, param={'$version': f'"{release}-{current_build}"'})
    jobs = result['results']
    for job in jobs:
        process_jenkins_job(job)
        print()

if __name__ == "__main__":
    args = parse_args()
    status, jobs = args.status.split(','), args.job.split(',')

    print("="*37)
    print(f"Platform Certification for {args.release}-{args.build}")
    print("="*37)
    print()
    
    job_summary(args.release, args.build, status, jobs, args.table)
    compare_build(args.release, args.build, args.previous, jobs, args.table)
    failure_summary(args.release, args.build, jobs)
