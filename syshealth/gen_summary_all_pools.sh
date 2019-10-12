#!/bin/bash 

OS="$1"
echo 'Pool : (Timedout) Unreachable + OK = Total'
echo "----------------------------------------"
TTIMED=0
INDEX=1
echo "">all_timedout.ini
for line in `cat vmpools_${OS}.txt|cut -f1 -d':'`
do
  POOL="$line"
  #echo ansible ${POOL} -i cbqe_vms_per_pool_${OS}.ini -u root -m ping
  #ansible ${POOL} -i cbqe_vms_per_pool_${OS}.ini -u root -m ping |tee ping_log_${OS}_${POOL}.txt
 
  TIMEDOUT="`egrep timed ping_log_${OS}_${POOL}.txt | cut -f4 -d':' |cut -f5 -d' '|wc -l|xargs`"
  UNREACH="`egrep UNREACHABLE ping_log_${OS}_${POOL}.txt | cut -f5 -d':' |cut -f5 -d' '|wc -l`"
  SUCCESS="`egrep SUCCESS ping_log_${OS}_${POOL}.txt | cut -f5 -d':' |cut -f5 -d' '|wc -l`"
  TOTAL="`egrep '=>' ping_log_${OS}_${POOL}.txt | cut -f5 -d':' |cut -f5 -d' '|wc -l`"
  echo " "
  echo $INDEX. $POOL : '('$TIMEDOUT')' $UNREACH +$SUCCESS = $TOTAL
  TTIMED=`expr $TIMEDOUT + $TTIMED`
  if [ ! "${TIMEDOUT}" = "0" ]; then
     echo "  Timedout VMs: "
     egrep timed ping_log_${OS}_${POOL}.txt | cut -f4 -d':' |cut -f5 -d' '
     egrep timed ping_log_${OS}_${POOL}.txt | cut -f4 -d':' |cut -f5 -d' ' >>all_timedout.ini
  fi
  echo " "
  INDEX=`expr $INDEX + 1`
done
echo "----------------------------------------"
UNIQUE=`sort all_timedout.ini|uniq|wc -l |xargs`
echo : $UNIQUE '('$TTIMED')' Unreachable + OK = Total

