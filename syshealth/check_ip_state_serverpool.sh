#!/bin/bash 

IPS=""
for line in `cat $1|egrep -v '\['`
do
  IPS=`echo $IPS '"'$line'",'`
done
echo  go run ../syshealthmonitor.go --action runquery --cbqueryurl http://172.23.105.177:8093/query/service 'select * from `QE-server-pool` where ipaddr in ['$IPS']'
go run ../syshealthmonitor.go --action runquery --cbqueryurl http://172.23.105.177:8093/query/service 'select * from `QE-server-pool` where ipaddr in ['$IPS']'
