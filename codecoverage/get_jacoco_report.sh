#!/bin/bash -x
JACOCO_EXEC=$1
if [ "$JACOCO_EXEC" = "" ]; then
  echo Usage: $0 jacoco_exec_path
  exit 1
fi
#java -jar ~/jacoco-0.8.4/lib/jacococli.jar report $1 --classfiles $HOME/.m2  --sourcefiles $HOME/cbws/analytics/cbas/cbas-server/src/main/java
#java -jar ~/jacoco-0.8.4/lib/jacococli.jar report $1 --classfiles $HOME/cbws/analytics/cbas/cbas-server/target/classes  --sourcefiles $HOME/cbws/analytics/cbas/cbas-server/src/main/java --html jacocohtml --csv jacoco.csv --xml jacoco.xml
for MOD in `echo cbas-common cbas-connector cbas-server`
do
 MOD_DIR=${MOD}-report
 mkdir $MOD_DIR
 java -jar ~/jacoco-0.8.4/lib/jacococli.jar report $1 --classfiles $HOME/cbws/analytics/cbas/${MOD}/target/classes  --sourcefiles $HOME/cbws/analytics/cbas/${MOD}/src/main/java --html ${MOD_DIR}/jacocohtml --csv ${MOD_DIR}/jacoco.csv --xml ${MOD_DIR}/jacoco.xml
done

# all modules
for MOD in `echo cbas-common cbas-connector cbas-server`
do
  ALL_CLASSES="$ALL_CLASSES --classfiles $HOME/cbws/analytics/cbas/${MOD}/target/classes"
  ALL_SRCS="$ALL_SRCS --sourcefiles $HOME/cbws/analytics/cbas/${MOD}/src/main/java"
done
MOD_DIR=all
mkdir $MOD_DIR
java -jar ~/jacoco-0.8.4/lib/jacococli.jar report $1 ${ALL_CLASSES} ${ALL_SRCS} --html ${MOD_DIR}/jacocohtml --csv ${MOD_DIR}/jacoco.csv --xml ${MOD_DIR}/jacoco.xml
