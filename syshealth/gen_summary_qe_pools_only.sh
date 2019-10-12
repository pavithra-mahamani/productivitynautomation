#!/bin/bash 

OS="$1"
USED_POOLS="$2"
echo 'Pool : (Timedout) Unreachable + OK = Total'
echo "----------------------------------------"
TTIMED=0
INDEX=1
OUT_TIMEDOUT=required_pools_timedout.ini
cat /dev/null>${OUT_TIMEDOUT}
for line in `cat vmpools_${OS}.txt|cut -f1 -d':'`
do
  POOL="$line"
  #echo ansible ${POOL} -i cbqe_vms_per_pool_${OS}.ini -u root -m ping
  #ansible ${POOL} -i cbqe_vms_per_pool_${OS}.ini -u root -m ping |tee ping_log_${OS}_${POOL}.txt
 
  REQ_POOL="`grep -iw $POOL ${USED_POOLS}`"
  if [ ! "$REQ_POOL" = "" ]; then
    echo RequiredPool: $REQ_POOL
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
     egrep timed ping_log_${OS}_${POOL}.txt | cut -f4 -d':' |cut -f5 -d' ' >>${OUT_TIMEDOUT}
    fi
    echo " "
    INDEX=`expr $INDEX + 1`
  fi
done
echo "----------------------------------------"
echo "[TIMEDOUT]">required_final_timedout.ini
sort $OUT_TIMEDOUT|uniq >>required_final_timedout.ini
UNIQUE=`cat required_final_timedout.ini|egrep -v '\[' |wc -l |xargs`
echo : $UNIQUE '('$TTIMED')' Unreachable + OK = Total

