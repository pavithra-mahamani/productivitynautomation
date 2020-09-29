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

HOSTS="$1"
if [ "$HOSTS" = "" ]; then
   echo "Usage: $0 HOSTS"
   echo "Example: $0 slaves.csv"
   echo "CSV file format: label1,label2"
   exit 1
fi

WORK_DIR=jenkins_logs
if [ ! -d $WORK_DIR ]; then
  mkdir -p $WORK_DIR
fi

JOB_URL=http://qa.sc.couchbase.com/computer
while IFS= read -r line
do
  for SL_NAME in `echo $line|sed 's/,/ /g'`
  do
    #echo curl -s -u ${JENKINS_USER}:${JENKINS_TOKEN} ${JOB_URL}/${SL_NAME}/api/json?pretty=true
    JSON=`curl -s -u ${JENKINS_USER}:${JENKINS_TOKEN} ${JOB_URL}/${SL_NAME}/api/json?pretty=true`
    HOST_NAME=`echo $JSON |jq '.description'|sed 's/"//g'|cut -f1 -d' '`
    echo $SL_NAME:$HOST_NAME
  done

  echo " "
done < $HOSTS
echo "Done! "
