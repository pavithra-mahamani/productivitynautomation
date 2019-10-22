#!/bin/bash -x
############################################################################
# Description: Get the IPs ssh ping and statistics
#
############################################################################

OS="$1"
USED_POOLS="$2"

if [ "$USED_POOLS" = "" ]; then
  echo "Usage $0 os used_pools_file"
  echo "Example: $0 centos file"
  exit 1
fi

echo 'Pool : (Timedout) Unreachable + OK = Total'
echo "----------------------------------------"
TTIMED=0
INDEX=1
OUT_TIMEDOUT=required_pools_timedout.ini
cat /dev/null>${OUT_TIMEDOUT}
cat vmpools_${OS}_counts.txt
for line in `cat vmpools_${OS}_counts.txt|cut -f1 -d':'`
do
  POOL="$line"
  NPOOL="`echo $line|sed -e 's/ //' -e 's/-//g'`"
  echo NPOOL
  LOG_FILE=ping_log_${OS}_${NPOOL}.txt
  echo ansible ${NPOOL} -i vmpools_${OS}_ips.ini -u root -m ping
  ansible ${NPOOL} -i vmpools_${OS}_ips.ini -u root -m ping >${LOG_FILE}
 
  REQ_POOL="`grep -iw $POOL ${USED_POOLS}`"
  if [ ! "$REQ_POOL" = "" ]; then
    echo RequiredPool: $REQ_POOL
    TIMEDOUT="`egrep timed ${LOG_FILE} | cut -f4 -d':' |cut -f5 -d' '|wc -l|xargs`"
    UNREACH="`egrep UNREACHABLE ${LOG_FILE} | cut -f5 -d':' |cut -f5 -d' '|wc -l`"
    SUCCESS="`egrep SUCCESS ${LOG_FILE}| cut -f5 -d':' |cut -f5 -d' '|wc -l`"
    TOTAL="`egrep '=>' ${LOG_FILE}| cut -f5 -d':' |cut -f5 -d' '|wc -l`"
    echo " "
    echo $INDEX. $POOL : '('$TIMEDOUT')' $UNREACH +$SUCCESS = $TOTAL
    TTIMED=`expr $TIMEDOUT + $TTIMED`
    if [ ! "${TIMEDOUT}" = "0" ]; then
     echo "  Timedout VMs: "
     egrep timed ${LOG_FILE} | cut -f4 -d':' |cut -f5 -d' '
     egrep timed ${LOG_FILE} | cut -f4 -d':' |cut -f5 -d' ' >>${OUT_TIMEDOUT}
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

