#!/bin/bash
#########################################
# Description: Cleanup high size folders on QE Jenkins
#
#########################################

BASE_DIR=/data/jenkins/jobs
SEL_DIRS="test_suite_executor-TAF test_suite_executor jepsen-durability-partition-daily-new jepsen-durability-rebalance-daily-new jepsen-durability-misc-daily-new jepsen-durability-kill-weekly-new test_suite_executor-docker-prod2"
for JOB_DIR in `echo $SEL_DIRS`
do
  CHECK_DIR=${BASE_DIR}/${JOB_DIR}/builds
  echo Checking and remove more than 1G files in ${CHECK_DIR}
  cd ${CHECK_DIR}
  rm `find ${CHECK_DIR} -size +1G`
done

