#!/bin/bash
################################################
# Description: Download the Jenkins jobs information
#    config.xml
#    build level - parameters, results, console log
#
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
   echo "Example: $0 testrunner-py3:108,testrunner-py3:107"
   exit 1
fi

WORK_DIR=jenkins_logs
if [ ! -d $WORK_DIR ]; then
  mkdir -p $WORK_DIR
fi
for JOB in `echo $JOBS|sed 's/,/ /g'`
do
  JOB_NAME="`echo $JOB|cut -f1 -d':'`"
  BUILDS="`echo $JOB|cut -f2 -d':'`"

  BUILD_START=`echo $BUILDS|cut -f1 -d'-'`
  BUILD_END=`echo $BUILDS|cut -f2 -d'-'`

  if [ ${BUILD_START} -gt ${BUILD_END} ]; then
     TEMP=${BUILD_START}
     BUILD_START=${BUILD_END}
     BUILD_END=${TEMP}
  fi

  INDEX=1

  BUILD=${BUILD_START}

  while (( ${BUILD} <= ${BUILD_END} ))
  do
   echo "...Getting ${JOB_NAME}/${BUILD} ..."
  JOB_DIR=$WORK_DIR/${JOB_NAME}_${BUILD}
  if [ ! -d ${JOB_DIR} ]; then
     mkdir $JOB_DIR
  fi
  CONFIG_FILE=$JOB_DIR/config.xml
  JOB_FILE=$JOB_DIR/jobinfo.json
  RESULT_FILE=$JOB_DIR/testresult.json
  LOG_FILE=$JOB_DIR/consoleText.txt

  # Download job config.xml
  echo curl -s -u ${JENKINS_USER}:${JENKINS_TOKEN} -o ${CONFIG_FILE} ${SERVER}/job/${JOB_NAME}/config.xml
  curl -s -u ${JENKINS_USER}:${JENKINS_TOKEN} -o ${CONFIG_FILE} ${SERVER}/job/${JOB_NAME}/config.xml

  #Download job details and parameters:
  echo curl -o ${JOB_FILE} ${SERVER}/job/${JOB_NAME}/${BUILD}/api/json?pretty=true
  curl -s -u ${JENKINS_USER}:${JENKINS_TOKEN} -o ${JOB_FILE} ${SERVER}/job/${JOB_NAME}/${BUILD}/api/json?pretty=true

  #Download test results:
  echo curl -o ${RESULT_FILE} ${SERVER}/job/${JOB_NAME}/${BUILD}/testReport/api/json?pretty=true
  curl -s -u ${JENKINS_USER}:${JENKINS_TOKEN} -o ${RESULT_FILE} ${SERVER}/job/${JOB_NAME}/${BUILD}/testReport/api/json?pretty=true

  #Download console log:
  echo curl -o ${LOG_FILE} ${SERVER}/job/${JOB_NAME}/${BUILD}/consoleText
  curl -s -u ${JENKINS_USER}:${JENKINS_TOKEN} -o ${LOG_FILE} ${SERVER}/job/${JOB_NAME}/${BUILD}/consoleText

  echo "Check artifacts at $JOB_DIR "
  BUILD=`expr ${BUILD} + 1`
  done
done
echo "Done! "
