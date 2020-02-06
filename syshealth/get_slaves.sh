#!/bin/bash 
######################################
# Description: Get the Jenkins Slave IPs
#
# 02/05/2020
######################################
LABEL="$1"
if [ "$LABEL" = "" ]; then
  echo "Usage: $0 LABEL"
  echo "Example: $0 P0"
  exit 1
fi
SLAVES_JSON="slaves.json"
CURL="curl -s -u jagadesh.munta:d861dbc62307405658a4b92c5ff8e38c"
JENKINS_URL="http://qa.sc.couchbase.com"
$CURL $JENKINS_URL/computer/api/json?pretty=true >$SLAVES_JSON

SLAVE_DETAILS=slave_details.txt
cat $SLAVES_JSON |jq '.computer[]|.displayName+":"+.assignedLabels[].name+":"+.offlineCauseReason'|egrep $LABEL  >$SLAVE_DETAILS

SLAVE_NAMES=slave_names.txt
cat $SLAVE_DETAILS |sed 's/"//g' |cut -f1,3 -d ':'|sort|uniq >$SLAVE_NAMES

INI_FILE=slaves.ini
STEXT=`echo $LABEL|tr -dc '[:alnum:]\n\r'`
echo "[slaves_$STEXT]" >$INI_FILE 

INDEX=1
while IFS= read -r line
do
  HOST_NAME=`echo $line|cut -f1 -d':'|sed 's/"//g'|xargs`
  #echo $CURL -d "script=println \"ifconfig eth0 \".execute().text" $JENKINS_URL/computer/$HOST_NAME/scriptText
  IP_ADDR=`$CURL -d "script=println \"ifconfig eth0 \".execute().text" $JENKINS_URL/computer/$HOST_NAME/scriptText|egrep inet|egrep 255|xargs|cut -f2 -d' '|sed 's/addr://g'`
  if [ "$IP_ADDR" = "" ]; then
    IP_ADDR=`$CURL -d "script=println \"ip address \".execute().text" $JENKINS_URL/computer/$HOST_NAME/scriptText|egrep -w inet|egrep 255 |xargs|cut -f2 -d' '|cut -f1 -d'/'`
  fi
  OFFLINE=`echo $line|cut -f2 -d':'|sed 's/"//g'|xargs`
  echo "$INDEX,$HOST_NAME,$IP_ADDR,$OFFLINE"
  INDEX=`expr $INDEX + 1`
  if [ ! "$IP_ADDR" = "" ]; then
    echo $IP_ADDR >>$INI_FILE
  fi
done <$SLAVE_NAMES
