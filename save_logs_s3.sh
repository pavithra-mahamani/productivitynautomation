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
echo "-->1) Getting the job Jenkins urls"
go run runanalyzer/runanalyzer.go --action savejoblogs ${CB_BUILD}
echo "-->2) Download Jenkins logs "
download_jenkins_jobs_csv.sh aborted_jobs.csv 
echo "-->3) Copy to AWS S3"
aws s3 cp jenkins_logs s3://cb-logs-qe/${CB_BUILD}/jenkins_logs --recursive

echo "Done!"
