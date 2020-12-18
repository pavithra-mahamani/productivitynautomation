"""
Usage: python changes_after_rerun.py <version>
Example: python changes_after_rerun.py 7.0.0-4023
"""
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster, ClusterOptions
import sys

version = sys.argv[1]

cluster = Cluster('couchbase://172.23.121.84', ClusterOptions(PasswordAuthenticator("Administrator", "password")))
bucket = cluster.bucket("greenboard")
doc = bucket.get("{}_server".format(version)).value

total_count = 0
after_rerun_total_count = 0

fail_count = 0
after_rerun_fail_count = 0

total_count_by_os = {}
after_rerun_total_count_by_os = {}

fail_count_by_os = {}
after_rerun_fail_count_by_os = {}

for os in doc["os"]:
    total_count_by_os[os] = 0
    after_rerun_total_count_by_os[os] = 0
    fail_count_by_os[os] = 0
    after_rerun_fail_count_by_os[os] = 0
    for component in doc["os"][os]:
        for job_name in doc["os"][os][component]:
            jobs = doc["os"][os][component][job_name]
            if len(jobs) == 1:
                # same for fresh run and rerun
                total_count += jobs[0]["totalCount"]
                after_rerun_total_count += jobs[0]["totalCount"]
                fail_count += jobs[0]["failCount"]
                after_rerun_fail_count += jobs[0]["failCount"]

                total_count_by_os[os] += jobs[0]["totalCount"]
                after_rerun_total_count_by_os[os] += jobs[0]["totalCount"]
                fail_count_by_os[os] += jobs[0]["failCount"]
                after_rerun_fail_count_by_os[os] += jobs[0]["failCount"]
            elif len(jobs) > 1:
                # fresh is last in array, latest rerun is first
                total_count += jobs[-1]["totalCount"]
                after_rerun_total_count += jobs[0]["totalCount"]
                fail_count += jobs[-1]["failCount"]
                after_rerun_fail_count += jobs[0]["failCount"]

                total_count_by_os[os] += jobs[-1]["totalCount"]
                after_rerun_total_count_by_os[os] += jobs[0]["totalCount"]
                fail_count_by_os[os] += jobs[-1]["failCount"]
                after_rerun_fail_count_by_os[os] += jobs[0]["failCount"]

pass_count = total_count - fail_count
after_rerun_pass_count = after_rerun_total_count - after_rerun_fail_count

print("Total")
print("Before rerun: {:.2f}% ({}/{})".format((pass_count / total_count) * 100, pass_count, total_count))
print("After rerun:  {:.2f}% ({}/{})".format((after_rerun_pass_count / after_rerun_total_count) * 100, after_rerun_pass_count, after_rerun_total_count))
print("\n")
print("By OS\n")

for os in doc["os"]:
    pass_count = total_count_by_os[os] - fail_count_by_os[os]
    after_rerun_pass_count = after_rerun_total_count_by_os[os] - after_rerun_fail_count_by_os[os]
    total_count = after_rerun_total_count_by_os[os]
    after_rerun_total_count = after_rerun_total_count_by_os[os]
    print(os)
    print("Before rerun: {:.2f}% ({}/{})".format((pass_count / total_count) * 100, pass_count, total_count))
    print("After rerun:  {:.2f}% ({}/{})\n".format((after_rerun_pass_count / after_rerun_total_count) * 100, after_rerun_pass_count, after_rerun_total_count))