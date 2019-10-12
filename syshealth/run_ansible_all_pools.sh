#!/bin/bash 

OS="$1"
for line in `cat vmpools_${OS}.txt|cut -f1 -d':'`
do
  POOL="$line"
  echo ansible ${POOL} -i cbqe_vms_per_pool_${OS}.ini -u root -m ping
  ansible ${POOL} -i cbqe_vms_per_pool_${OS}.ini -u root -m ping |tee ping_log_${OS}_${POOL}.txt
done
