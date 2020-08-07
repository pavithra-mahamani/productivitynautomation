#!/bin/bash
##########################################################################
# Description: Get the runtime test details os certification tests for a given build
#
# Dependencies: jq tool
# Examples:
# ./runtime_stats_oscer.sh 7.0.0-2741
##########################################################################

CB_VERSION="$1"
USER_NAME="$2"
USER_PWD="$3"
RESULTS_JSON=results.json
JQ_TOOL=~/jq
if [ "${CB_VERSION}" = "" ]; then
  echo Usage: $0 CB_VERSION
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
  echo ,,,TestCase,TestCount,ExecutionTime
  cat ${RESULTS_JSON} | ${JQ_TOOL} -r  '.suites[]|",,,"+.name + "," + (.cases|length|tostring) + "," + (.duration |tostring)'
  TEST_COUNT=`cat ${RESULTS_JSON} | ${JQ_TOOL} '.failCount + .passCount + .skipCount'`
  TOTAL_TIME=`cat ${RESULTS_JSON} | ${JQ_TOOL} '.duration'`
  echo 
  echo ",,,TOTAL,${TEST_COUNT},${TOTAL_TIME}"
}

get_os_cert_jobs()
{
 BUILD="$1"
 USER="$2"
 PASSWD="$3"
 curl -s -u${USER}:${PASSWD} -o ${BUILD}_os_certify.json -d 'statement=select * from server where `build`='"'${BUILD}'"' and component="OS_CERTIFY"' 'http://172.23.109.245:8093/query/service'
 cat ${BUILD}_os_certify.json|${JQ_TOOL} -r '.results[].server|.os +","+(.name + "," + .url + "," + (.build_id|tostring))' |sort >${BUILD}_os_certify.csv
 declare -A SUMMARY
 declare -A ALL_PLATFORMS
 for LINE in `cat ${BUILD}_os_certify.csv`
 do
   NAME=`echo $LINE|cut -f2 -d','`
   OS=`echo $NAME|cut -f1 -d'-'`
   URL=`echo $LINE|cut -f3 -d','`
   BUILD_ID=`echo $LINE|cut -f4 -d','`
   echo 
   echo ${BUILD},${OS},${NAME},,,
   get_results_json ${URL}${BUILD_ID} 
   IS_NOT_FOUND="`grep '404 Not Found' ${RESULTS_JSON}`"
   if [ ! "${IS_NOT_FOUND}" = "" ]; then
     get_results_json http://cb-logs-qe.s3-website-us-west-2.amazonaws.com/${BUILD}/jenkins_logs/test_suite_executor/${BUILD_ID}
   fi
   get_runtime
   #summary
   
   ALL_PLATFORMS[${OS}]="${OS}"
   if [ "${SUMMARY[${OS}_COUNT]}" = "" ]; then
      SUMMARY[${OS}_COUNT]=${TEST_COUNT}
   else
      SUMMARY[${OS}_COUNT]=`echo "${SUMMARY[${OS}_COUNT]} + ${TEST_COUNT}"|bc`
   fi
   if [ "${SUMMARY[${OS}_TIME]}" = "" ]; then
      SUMMARY[${OS}_TIME]=${TOTAL_TIME}
   else
      SUMMARY[${OS}_TIME]=`echo "${SUMMARY[${OS}_TIME]} + ${TOTAL_TIME}"|bc`
   fi
 done
 ALL_OS=""
 for OS in `echo ${!ALL_PLATFORMS[@]}|xargs -n1 |sort|xargs`
 do
    if [ "${ALL_OS}" = "" ]; then
      ALL_OS="${OS}"
    else
      ALL_OS="`echo ${ALL_OS},,${OS}`"
    fi
 done
 ALL_DATA=""
 ALL_HEADER=""
 for OS in `echo ${!ALL_PLATFORMS[@]}|xargs -n1 |sort|xargs`
 do
    if [ "${ALL_DATA}" = "" ]; then
       ALL_DATA="${SUMMARY[${OS}_COUNT]},${SUMMARY[${OS}_TIME]}"
       ALL_HEADER="TestsCount,TotalTime"
    else
       ALL_DATA="${ALL_DATA},${SUMMARY[${OS}_COUNT]},${SUMMARY[${OS}_TIME]}"
       ALL_HEADER="${ALL_HEADER},TestsCount,TotalTime"
    fi
 done
 echo ${ALL_OS} >os_cert_summary.csv
 echo ${ALL_HEADER}>>os_cert_summary.csv
 echo ${ALL_DATA}>>os_cert_summary.csv
}

all()
{
 get_os_cert_jobs ${CB_VERSION} ${USER_NAME} ${USER_PWD}
}

all

