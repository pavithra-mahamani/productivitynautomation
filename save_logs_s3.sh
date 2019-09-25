#!/bin/bash
CB_BUILD=${1}
if [ "${CB_BUILD}" = "" ]; then
   echo "*** Save Testrunner jobs Jenkins logs to S3 ***"
   echo "Usage: $0 CB_BUILD"
   exit 1
fi

if [ ! -d helperscripts ]; then
  git clone http://github.com/jdmuntacb/helperscripts.git
  cd helperscripts
fi
SCRIPTS_DIR=`pwd`
mkdir ${CB_BUILD}
cd ${CB_BUILD}
echo "-->1) Getting the job Jenkins urls"
go run $SCRIPTS_DIR/runanalyzer/runanalyzer.go --action savejoblogs ${CB_BUILD}
echo "-->2) Download Jenkins logs "
echo $PWD
$SCRIPTS_DIR/download_jenkins_jobs_csv.sh all_jobs.csv 
echo "-->3) Copy to AWS S3"
aws s3 cp jenkins_logs s3://cb-logs-qe/${CB_BUILD}/jenkins_logs --recursive
cd $SCRIPTS_DIR
echo "Done!"
