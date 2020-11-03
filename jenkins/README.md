# Jenkins Scripts

## Jenkins Helper

Allows you to get a list of slaves, running builds or queued builds as well as whether a job is running

```
Usage: jenkinshelper.py [options]

Options:
  -h, --help            show this help message and exit
  -v VERSION, --version=VERSION
  -c CONFIGFILE, --config=CONFIGFILE
                        Configuration file
  -l LOGLEVEL, --log-level=LOGLEVEL
                        e.g -l info,warning,error
  -u BUILD_URL_TO_CHECK, --url=BUILD_URL_TO_CHECK
                        Build URL to check
  -i IGNORE_PARAMS, --ignore=IGNORE_PARAMS
                        Igore parameters list
  -j, --is_job_running  Check if a job is running
  -r, --get_running_builds
                        Get running builds
  -q, --get_queued_builds
                        Get queued builds
  -s, --get_slaves      Get slaves
```

## Hanging Jobs

Allows you to stop jobs that have not had console output for a certain amount of time.

```
Usage: hanging_jobs.py [options]

Options:
  -h, --help            show this help message and exit
  -c CONFIGFILE, --config=CONFIGFILE
                        Configuration file
  -u BUILD_URL_TO_CHECK, --url=BUILD_URL_TO_CHECK
                        Build URL to check
  -t TIMEOUT, --timeout=TIMEOUT
                        No console output timeout (minutes)
  -e EXCLUDE, --exclude=EXCLUDE
                        Regular expression of job names to exclude
  -i INCLUDE, --include=INCLUDE
                        Regular expression of job names to include
  -p, --print           Just print hanging jobs, don't stop them
```

## Example

```
(env) jakerawsthorne@REML0715 jenkins % python hanging_jobs.py --print
2020-11-03 12:25:32,929 - hanging_jobs - INFO - Given build url=http://qa.sc.couchbase.com
2020-11-03 12:25:32,929 - jenkinshelper - INFO - Jenkins url:http://qa.sc.couchbase.com
2020-11-03 12:25:32,929 - jenkinshelper - INFO - Loading config from .jenkinshelper.ini
<Section: jenkins>
2020-11-03 12:25:32,930 - jenkinshelper - INFO - Jenkins user:jake.rawsthorne,token:************************
2020-11-03 12:26:41,996 - hanging_jobs - INFO - http://qa.sc.couchbase.com/job/centos-systest-launcher-2/828/ is hanging (last console output: 2020-11-03 11:22:23+00:00 (64.32 minutes ago)
2020-11-03 12:26:46,095 - hanging_jobs - INFO - http://qa.sc.couchbase.com/job/test_suite_executor-TAF/67784/ is hanging (last console output: 2020-11-03 10:51:25+00:00 (95.35 minutes ago)
2020-11-03 12:26:53,443 - hanging_jobs - INFO - http://qa.sc.couchbase.com/job/test_suite_executor-TAF/67781/ is hanging (last console output: 2020-11-03 11:04:22+00:00 (82.52 minutes ago)
2020-11-03 12:26:53,785 - hanging_jobs - WARNING - timestamp not found for http://qa.sc.couchbase.com/job/k8s-cbop-gke-validation-2.0.x/200/
2020-11-03 12:26:54,117 - hanging_jobs - WARNING - timestamp not found for http://qa.sc.couchbase.com/job/k8s-cbop-aks-sanity-2.0.x/194/
2020-11-03 12:26:54,453 - hanging_jobs - WARNING - timestamp not found for http://qa.sc.couchbase.com/job/k8s-cbop-eks-sanity-2.0.x/187/
2020-11-03 12:26:54,785 - hanging_jobs - WARNING - timestamp not found for http://qa.sc.couchbase.com/job/cbop-oc-4.x-sanity-2.0.x/42/
2020-11-03 12:26:56,368 - hanging_jobs - WARNING - timestamp not found for http://qa.sc.couchbase.com/job/test_suite_dispatcher/38227/
2020-11-03 12:26:56,724 - hanging_jobs - WARNING - timestamp not found for http://qa.sc.couchbase.com/job/test_suite_dispatcher/39693/
2020-11-03 12:26:57,743 - hanging_jobs - INFO - http://qa.sc.couchbase.com/job/test_suite_executor/273816/ is hanging (last console output: 2020-11-02 22:41:55+00:00 (825.05 minutes ago)
2020-11-03 12:27:00,134 - hanging_jobs - INFO - http://qa.sc.couchbase.com/job/test_suite_executor/273868/ is hanging (last console output: 2020-11-03 05:34:07+00:00 (412.89 minutes ago)
2020-11-03 12:27:00,970 - hanging_jobs - INFO - http://qa.sc.couchbase.com/job/test_suite_executor/273870/ is hanging (last console output: 2020-11-03 08:29:39+00:00 (237.37 minutes ago)
2020-11-03 12:27:01,482 - hanging_jobs - INFO - http://qa.sc.couchbase.com/job/test_suite_executor/273837/ is hanging (last console output: 2020-11-02 21:58:13+00:00 (868.81 minutes ago)
2020-11-03 12:27:02,322 - hanging_jobs - INFO - http://qa.sc.couchbase.com/job/test_suite_executor/273874/ is hanging (last console output: 2020-11-03 06:15:39+00:00 (371.39 minutes ago)
2020-11-03 12:27:05,392 - hanging_jobs - INFO - http://qa.sc.couchbase.com/job/test_suite_executor/273766/ is hanging (last console output: 2020-11-02 17:58:47+00:00 (1108.31 minutes ago)
2020-11-03 12:27:17,578 - hanging_jobs - INFO - http://qa.sc.couchbase.com/job/test_suite_executor/273791/ is hanging (last console output: 2020-11-02 21:52:28+00:00 (874.83 minutes ago)
2020-11-03 12:27:18,779 - hanging_jobs - INFO - http://qa.sc.couchbase.com/job/test_suite_executor/273823/ is hanging (last console output: 2020-11-03 02:16:51+00:00 (610.46 minutes ago)
2020-11-03 12:32:36,341 - hanging_jobs - INFO - http://qa.sc.couchbase.com/job/test_suite_executor-dynvm/3111/ is hanging (last console output: 2020-11-02 19:39:29+00:00 (1013.12 minutes ago)
```