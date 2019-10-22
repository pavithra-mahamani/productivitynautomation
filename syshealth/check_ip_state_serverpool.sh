#!/bin/bash 

if [ "$1" = "" ]; then
    echo "Usage: $0 IPfile"
    exit 1
fi

IPS=""
for line in `cat $1|egrep -v '\['`
do
  IPS=`echo $IPS '"'$line'",'`
done
IPS=${IPS%?}
echo  go run syshealthmonitor.go --action runquery --cbqueryurl http://172.23.105.177:8093/query/service 'select * from `QE-server-pool` where ipaddr in ['$IPS']'
go run syshealthmonitor.go --action runquery --cbqueryurl http://172.23.105.177:8093/query/service 'select * from `QE-server-pool` where ipaddr in ['$IPS']'
