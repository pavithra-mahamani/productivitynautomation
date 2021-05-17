#!/bin/bash
################################################################
# Description: 
#  1) Get the list of aborted and failed from fresh regression run
#  2) Common IPs across the failed ones
# Note: Download xenhosts summary from https://docs.google.com/spreadsheets/d/1vAJWICyn21mBo61ZOKaIykEcG4Nii_O89sFcHmVE7pc/edit?usp=sharing
#                                 to qe_xen_hosts_info_summary.csv 
################################################################
CB_BUILD_LIST="$1"
if [ "${CB_BUILD_LIST}" == "" ]; then
  echo "Get the list of fresh aborted and failed run details..."
  echo "Usage: $0 CB_BUILD_LIST"
  exit 1
fi

if [ ! -f qe_xen_hosts_info_summary.csv ]; then
  echo "Download xenhosts summary (.csv) from https://docs.google.com/spreadsheets/d/1vAJWICyn21mBo61ZOKaIykEcG4Nii_O89sFcHmVE7pc/view 
      to qe_xen_hosts_info_summary_serverpool.csv"
  exit 1
fi

WORK_DIR=`date +'%m%d%y-%H%M%S'`
SCRIPT_DIR=`dirname $0`
CUR_DIR=$PWD
mkdir $WORK_DIR
cd $WORK_DIR
INDEX=0
for CB_BUILD in `echo ${CB_BUILD_LIST}|sed 's/,/ /g'`
do
  INDEX=`expr ${INDEX} + 1`
  echo "Getting fresh run aborted/failed details for #${INDEX}. ${CB_BUILD} ..."
  FAILED_FILE="failed_${CB_BUILD}.csv"
  time python3 $SCRIPT_DIR/get_fresh_failed_list.py ${CB_BUILD} $CUR_DIR/qe_xen_hosts_info_summary.csv |tee ${FAILED_FILE}
  cat ${FAILED_FILE} |cut -f6 -d',' |egrep xcp|xargs -n1 |sort |uniq -c |sort -r|xargs -n2 | sed 's/ /,/g' > failed_xenhosts_${CB_BUILD}.csv
  cat ${FAILED_FILE} |cut -f5 -d',' |xargs -n1 |sort |uniq -c |sort -r|xargs -n2 | sed 's/ /,/g' > failed_ips_${CB_BUILD}.csv

  echo "Generated ${FAILED_FILE}, failed_ips_${CB_BUILD}.csv, failed_xenhosts_${CB_BUILD}.csv"
done
# commonly failed VMs
cat failed_ips*.csv |cut -f2 -d',' |sort|uniq -c|sort -r|xargs -n2|egrep "^$INDEX"|cut -f2 -d' ' >summary_common_failed_ips.txt
cat failed_xenhosts*.csv |cut -f2 -d',' |sort|uniq -c|sort -r|xargs -n2|egrep "^$INDEX"|cut -f2 -d' ' >summary_common_failed_xenhosts.txt
# comm -12 failed_ips.csv failed_ips_5071.csv | comm -12 - failed_ips_5017.csv | comm -12 - failed_ips_4960.csv
echo "----- Common IPs list ---"
cat summary_common_failed_ips.txt
echo "----- Total count: `cat summary_common_failed_ips.txt |wc -l`"
cd $CUR_DIR
echo "NOTE: See the generated files under $WORK_DIR/ directory.  `ls $WORK_DIR |xargs`"
echo '------'