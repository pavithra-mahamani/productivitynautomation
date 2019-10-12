#!/bin/bash 
INDEX=1
COUNT=`wc -l $1`
for line in `cat $1`
do
  echo $INDEX/$COUNT. sshpass -p couchbase ssh-copy-id root@$line
  sshpass -p couchbase ssh-copy-id root@$line
  INDEX=`expr $INDEX + 1`
done
