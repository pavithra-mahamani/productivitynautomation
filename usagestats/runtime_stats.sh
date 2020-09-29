#!/bin/bash
##########################################################################
# Description: Get the runtime test details from junit test results
#
# Dependencies: jq tool
# Examples:
# ./runtime_stats.sh http://cb-logs-qe.s3-website-us-west-2.amazonaws.com/7.0.0-2746/jenkins_logs/test_suite_executor/242411/
# ./runtime_stats.sh http://cb-logs-qe.s3-website-us-west-2.amazonaws.com/7.0.0-2746/jenkins_logs/test_suite_executor/242411
# ./runtime_stats.sh http://cb-logs-qe.s3-website-us-west-2.amazonaws.com/7.0.0-2746/jenkins_logs/test_suite_executor/242411/testresult.json
# ./runtime_stats.sh http://qa.sc.couchbase.com/job/test_suite_executor-TAF/47414
##########################################################################

JOB_URL="$1"
RESULTS_JSON=results.json
JQ_TOOL=~/jq
if [ "${JOB_URL}" = "" ]; then
  echo Usage: $0 jenkins_job_url_or_save_logs_s3url
  exit 1
fi

get_results_json()
{
  if [[ "$1" = */ ]]; then
    URL=${1%?}
  else
    URL=${1}
  fi
  if [[ "${URL}" = *json ]]; then
    curl -s -o ${RESULTS_JSON} "${URL}"
  elif [[ "$1" = *cb-logs-qe.s3* ]]; then
    curl -s -o ${RESULTS_JSON} "${URL}/testresult.json"
  else
    curl -s -o ${RESULTS_JSON} "${URL}/testReport/api/json?pretty=true"
  fi
}

get_runtime()
{
  echo TestCase,TestCount,ExecutionTime
  cat ${RESULTS_JSON} | ${JQ_TOOL} -r  '.suites[]|.name + "," + (.cases|length|tostring) + "," + (.duration |tostring)'
  TEST_COUNT=`cat ${RESULTS_JSON} | ${JQ_TOOL} '.failCount + .passCount + .skipCount'`
  TOTAL_TIME=`cat ${RESULTS_JSON} | ${JQ_TOOL} '.duration'`
  echo 
  echo "TOTAL,${TEST_COUNT},${TOTAL_TIME}"
}

all()
{
 get_results_json ${JOB_URL}
 get_runtime
}

all
