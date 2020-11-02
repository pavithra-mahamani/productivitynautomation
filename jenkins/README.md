# Jenkins Scripts

jenkinshelper.py allows you to get a list of slaves, running builds or queued builds as well as whether a job is running

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

hanging_jobs.py allows you to stop jobs that have not had console output for a certain amount of time.

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