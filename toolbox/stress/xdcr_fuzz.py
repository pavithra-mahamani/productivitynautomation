import subprocess
import threading
import random
import time

host_rep_map = {}
host_bkt_map = {}

# TODO: add ini file parsing
hosts = ["x.x.x.x",
         "y.y.y.y"
         ]

settings = {"checkpointInterval": range(60, 14400, 100),
            "compressionType": ["Auto"],
            "desiredLatency": range(100, 10000, 100),
            "docBatchSizeKb": range(10, 10000, 100),
            "failureRestartInterval": range(1, 300, 10),
            "filterExpression": ["REGEXP_CONTAINS(META().id,'0$')"],
            "filterSkipRestream": [True, False],
            "filterVersion": [0, 1],
            "goMaxProcs": range(1, 100, 1),
            "logLevel": ["Info", "Debug"],
            "networkUsageLimit": range(0, 1000000, 100),
            "optimisticReplicationThreshold": range(0, 20 * 1024 * 1024, 1024),
            "pauseRequested": [True, False],
            "priority": ["High", "Medium", "Low"],
            "sourceNozzlePerNode": range(1, 100, 10),
            "statsInterval": range(200, 600000, 100),
            "targetNozzlePerNode": range(1, 100, 10),
            "type": ["xmem", "continuous"],
            "workerBatchSize": range(500, 10000, 100)
            }

operations = ["create_replication",
              "delete_replication",
              "delete_buckets",
              "load_bucket",
              "change_setting"
              ]

port = "8091"
username = "Administrator"
password = "password"


class Command(object):
    def __init__(self, cmd):
        self.cmd = cmd
        self.process = None
        self.ret = []
        self.start = 0
        self.end = 0

    def run(self, timeout):
        def target():
            print("Executing cmd " + self.cmd)
            self.start = time.time()
            self.process = subprocess.Popen(self.cmd, shell=True,
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.ret = self.process.communicate()[0].decode().split('\n')

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout)
        self.end = time.time()
        try:
            if thread.is_alive():
                print("Terminating process after {0}s".format(int(self.end - self.start)))
                self.process.terminate()
        except Exception as e:
            print("Unable to terminate process {0}".format(e.message))

        thread.join()
        return self.ret


def load_bucket(host, bucket):
    print("Loading bucket {0} on {1}".format(bucket, host))
    intervals = range(1, 20)
    count = 10
    rand_intervals = random.sample(intervals, count)
    rand_intervals.sort()
    for interval in rand_intervals:
        execute_cmd("/opt/couchbase/bin/cbworkloadgen -n " + host + ':' + port +
                    ' -u ' + username + ' -p ' + password + ' -b ' + bucket +
                    " -r .5 --prefix=doc-" + str(interval) +
                    "-t 10 -i 100 -s 10 --xattr -j -l", interval)


def execute_cmd(cmd, timeout=60):
    command = Command(cmd)
    return command.run(timeout=timeout)


def refresh_maps():
    for host in hosts:
        repl_ids = []
        replications = execute_cmd("/opt/couchbase/bin/couchbase-cli xdcr-replicate -c " + host +
                                   ' -u ' + username + ' -p ' + password + " --list")
        for repl in replications:
            if repl.startswith("stream"):
                repl_ids.append(repl.split()[-1].replace('/', "%2F"))
        host_rep_map[host] = repl_ids
        bkts = []
        buckets = execute_cmd("/opt/couchbase/bin/couchbase-cli bucket-list -c " + host +
                              ' -u ' + username + ' -p ' + password)
        for bkt in buckets:
            if bkt.startswith("cb"):
                bkts.append(bkt.rstrip())
        host_bkt_map[host] = bkts
    print(host_rep_map)
    print(host_bkt_map)


def __get_bucket(host):
    if host_bkt_map[host]:
        bucket = random.choice(host_bkt_map[host])
    else:
        bucket = "cb" + str(random.randint(0, 1000))
        print("Creating bucket {0} on {1}".format(bucket, host))
        execute_cmd("/opt/couchbase/bin/couchbase-cli bucket-create -c " + host + ':' + port +
                    " --username " + username + " --password " + password +
                    " --bucket " + bucket + " --bucket-ramsize 100 --bucket-type couchbase")
    return bucket


def delete_buckets(host, flush=False):
    for bucket in host_bkt_map[host]:
        if flush:
            print("Flushing bucket {0} on {1}".format(bucket, host))
            execute_cmd("curl -X POST -u " + username + ':' + password + " http://" + host + ':' + port +
                        "/pools/default/buckets/" + bucket + "/controller/doFlush")
        else:
            print("Deleting bucket {0} on {1}".format(bucket, host))
            execute_cmd("curl -X DELETE -u " + username + ':' + password + " http://" + host + ':' + port +
                        "/pools/default/buckets/" + bucket)
    refresh_maps()


def _create_remote_ref(host):
    remote = random.choice(hosts)
    while remote == host:
        remote = random.choice(hosts)
    src_bkt = __get_bucket(host)
    dest_bkt = __get_bucket(remote)
    existing_remotes = execute_cmd("curl -u " + username + ':' + password + " http://" + host + ':' + port +
                                   "/pools/default/remoteClusters")
    if not remote in existing_remotes:
        print("Creating remote cluster ref {0}".format(host + "to" + remote))
        execute_cmd("curl -v -u " + username + ':' + password + " http://" + host + ':' + port +
                    "/pools/default/remoteClusters -d name=" + host + "to" + remote +
                    " -d hostname=" + remote + ':' + port + " -d username=" + username + " -d password=" + password)
    return (host + "to" + remote, src_bkt, dest_bkt)


def create_replication(host):
    ref, src_bkt, dest_bkt = _create_remote_ref(host)
    print("Creating replication on {0}".format(host))
    execute_cmd("curl -X POST -u " + username + ':' + password + " http://" + host + ':' + port +
                "/controller/createReplication -d fromBucket=" + src_bkt + " -d toCluster=" + ref +
                " -d toBucket=" + dest_bkt + " -d replicationType=continuous")
    refresh_maps()


def delete_replication(host, replication):
    print("Deleting replication {0} from {1}".format(replication, host))
    execute_cmd("curl -X POST -u " + username + ':' + password + " http://" + host + ':' + port +
                "/controller/cancelXDCR/" + replication + " -X DELETE")
    refresh_maps()


def change_setting(host, replication, setting, newval):
    print("Changing {0} to {1} for replication {2} on {3}".format(setting, newval, replication, host))
    execute_cmd("curl -X POST -u " + username + ':' + password + " http://" + host + ':' + port +
                "/settings/replications/" + replication + ' -d ' + setting + '=' + str(newval))


def dispatch():
    host = random.choice(hosts)
    operation = random.choice(operations)
    if operation.startswith("create"):
        create_replication(host)
    else:
        while not host_rep_map[host]:
            host = random.choice(hosts)
            create_replication(host)
            time.sleep(10)
        rep = random.choice(host_rep_map[host])
    if operation == "delete_replication":
        delete_replication(host, rep)
    elif operation == "delete_buckets":
        delete_buckets(host)
    elif operation == "flush_buckets":
        delete_buckets(host, flush=True)
    elif operation.startswith("change"):
        setting = random.choice(settings.keys())
        val = random.choice(settings[setting])
        change_setting(host, rep, setting, val)
    elif operation == "load_bucket":
        load_bucket(host, __get_bucket(host))


if __name__ == "__main__":
    refresh_maps()
    host = random.choice(hosts)
    create_replication(host)
    while True:
        dispatch()
        time.sleep(10)
