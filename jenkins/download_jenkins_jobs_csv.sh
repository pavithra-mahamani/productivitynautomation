#!/bin/bash
################################################
# Description: Download the results from jenkins
#
# jagadesh.munta@couchbase.com
################################################

FILE=.jenkins_env.properties
ENV_FILE=${HOME}/${FILE}
if [ -f $ENV_FILE ]; then
  . $ENV_FILE
else
  echo "JENKINS_USER=youruser" >$ENV_FILE
  echo "JENKINS_TOKEN=yourusertoken" >>$ENV_FILE
  echo "SERVER=http://yourjenkinsserver" >>$ENV_FILE
  . $ENV_FILE
fi

if [ "${JENKINS_USER}" = "youruser" ]; then
   echo "ERROR: Please fill the Jenkins environment values in ${ENV_FILE}"
   exit 1
fi
echo "JENKINS_USER=${JENKINS_USER}"
echo "JENKINS_SERVER=${SERVER}"

JOBS="$1"
if [ "$JOBS" = "" ]; then
   echo "Usage: $0 JOBS"
   echo "Example: $0 aborted_jobs.csv"
   echo "CSV file format: NAME,JOB_URL,BUILD"
   exit 1
fi

WORK_DIR=jenkins_logs
if [ ! -d $WORK_DIR ]; then
  mkdir -p $WORK_DIR
fi

INDEX=1
while IFS= read -r line
do
  TS_NAME="`echo $line|xargs|cut -f1 -d','|tr -dc '[[:print:]]'`"
  JOB_URL="`echo $line|xargs|cut -f2 -d','|tr -dc '[[:print:]]'`"
  BUILD="`echo $line|xargs|cut -f3 -d','|tr -dc '[[:print:]]'`"

  echo "${INDEX}. TS_NAME=${TS_NAME}, JOB_URL=${JOB_URL}, BUILD=${BUILD};"
  echo "--Getting ${JOB_URL}/${BUILD} ..."
  #check in case aws s3 url
  IS_AWS_URL="`echo $JOB_URL |egrep '.s3.'`"
  if [ ! "${IS_AWS_URL}" = "" ]; then
     echo "Warning: Skipping the non Jenkins or AWS url to download the logs..."
     echo ""
     INDEX=`expr $INDEX + 1`
     continue
  fi

  #JOB_DIR=$WORK_DIR/${TS_NAME}_${BUILD}
  JOB_NAME="`echo $JOB_URL|rev|cut -f2 -d'/'|rev`"
  if [ "${JOB_NAME}" = "${BUILD}" ]; then
    JOB_NAME="`echo $JOB_URL|rev|cut -f3 -d'/'|rev`"
    JOB_URL=${JOB_URL}..
  fi
  JOB_DIR=$WORK_DIR/${JOB_NAME}/${BUILD}
  if [ ! -d ${JOB_DIR} ]; then
     mkdir -p $JOB_DIR
  fi
  CONFIG_FILE=$JOB_DIR/config.xml
  JOB_FILE=$JOB_DIR/jobinfo.json
  RESULT_FILE=$JOB_DIR/testresult.json
  LOG_FILE=$JOB_DIR/consoleText.txt
  ARCHIVE_ZIP_FILE=$JOB_DIR/archive.zip

  JENKINS_SERVER_NAME=`echo $JOB_URL|cut -f3 -d'/' |cut -f1 -d'.'|tr '[a-z]' '[A-Z]'`
  echo $JENKINS_SERVER_NAME
  USER_VAR="${JENKINS_SERVER_NAME}_JENKINS_USER"
  TOKEN_VAR="${JENKINS_SERVER_NAME}_JENKINS_TOKEN"
  JENKINS_USER=${!USER_VAR}
  JENKINS_TOKEN=${!TOKEN_VAR}

  # Download job config.xml
  #echo curl -s -u ${JENKINS_USER}:${JENKINS_TOKEN} -o ${CONFIG_FILE} ${JOB_URL}/config.xml
  curl -s -u ${JENKINS_USER}:${JENKINS_TOKEN} -o ${CONFIG_FILE} ${JOB_URL}/config.xml

  #Download job details and parameters:
  #echo curl -s -u ${JENKINS_USER}:${JENKINS_TOKEN} -o ${JOB_FILE} ${JOB_URL}/${BUILD}/api/json?pretty=true
  curl -s -u ${JENKINS_USER}:${JENKINS_TOKEN} -o ${JOB_FILE} ${JOB_URL}/${BUILD}/api/json?pretty=true

  #Download test results:
  #echo curl -s -u ${JENKINS_USER}:${JENKINS_TOKEN} -o ${RESULT_FILE} ${JOB_URL}/${BUILD}/testReport/api/json?pretty=true
  curl -s -u ${JENKINS_USER}:${JENKINS_TOKEN} -o ${RESULT_FILE} ${JOB_URL}/${BUILD}/testReport/api/json?pretty=true

  #Download console log:
  #echo curl -s -u ${JENKINS_USER}:${JENKINS_TOKEN} -o ${LOG_FILE} ${JOB_URL}/${BUILD}/consoleText
  curl -s -u ${JENKINS_USER}:${JENKINS_TOKEN} -o ${LOG_FILE} ${JOB_URL}/${BUILD}/consoleText

  #Download build artifacts - skipping for now as this is taking long time
  #curl -s -u ${JENKINS_USER}:${JENKINS_TOKEN} -o ${ARCHIVE_ZIP_FILE} ${JOB_URL}/${BUILD}/artifact/*zip*/archive.zip

  echo "Check artifacts at $JOB_DIR "
  echo " "
  INDEX=`expr $INDEX + 1`
done < $JOBS
echo "Done! "
