#!/bin/bash -x
#####################################################
# Description: Code coverage analysis helper script
#
#####################################################

clean()
{
  if [ -d $WORKSPACE/cbws ]; then
     rm -rf $WORKSPACE/cbws/*
  fi  
}
repo_sync()
{
  if [ ! -d $WORKSPACE/cbws ]; then
    mkdir $WORKSPACE/cbws
  fi
  cd $WORKSPACE/cbws
  repo init -u git://github.com/couchbase/manifest.git -m couchbase-server/mad-hatter.xml  -g all
  repo sync
}

build_analytics()
{
    echo "*** Building: analytics ***"
    #Pre-build:
    export CB_MAVEN_REPO_LOCAL=$1

    mkdir -p build
    cd build

    cmake -D CB_DOWNLOAD_JAVA=1 -D CB_DOWNLOAD_DEPS=1 ..
    cd ..

    cp -R $HOME/ClusterTestBase.java ./analytics/cbas/cbas-server/src/test/java/com/couchbase/analytics/test/common/ClusterTestBase.java
    make -j8 || make
    echo ##### end make ####

    mvn -f analytics/cbas/pom.xml -B install -rf :cbas-test -pl :cbas-cbserver-test -am -Drat.skip -Dsource-format.skip -DskipTests -Dfile.encoding=utf-8 -Dmaven.repo.local=$CB_MAVEN_REPO_LOCAL

    echo ##### end test build


    #Build:
    export MAVEN_OPTS=-Xmx4g
    #mvn -f analytics/cbas/pom.xml -B verify -P jenkins,cbas-cbcluster-test -pl :cbas-cbserver-test
    mvn -f analytics/cbas/pom.xml -B verify -P cbas-cbcluster-test -pl :cbas-cbserver-test -Dmaven.repo.local=$CB_MAVEN_REPO_LOCAL
    
}

enable_jacoco()
{
  curl -v -u Administrator:password -X PUT -d "jvmArgs=-javaagent:/Users/jagadeshmunta/jacoco/jacocoagent.jar" http://localhost:8095/analytics/config/service
}

gen_jacoco_report()
{
  java -jar jacococli.jar report $HOME/jacoco.exec --xml ~/jacocoreports/jacoco.xml --csv ~/jacocoreports/jacoco.csv --html ~/jacocoreports/html --classfiles $HOME/.m2/com/couchbase/analytics/

}

run_scanner()
{
  ./sonar-scanner -Dsonar.projectKey=samplejacoco -Dsonar.host.url=http://172.23.105.131:9000 -Dsonar.login=5517d08da769a1fccd8551e6b4431d03baafd005 -Dsonar.coverage.jacoco.xmlReportPaths=/Users/jagadeshmunta/jacocoreports/jacoco.xml -Dsonar.sources=/Users/jagadeshmunta/cbws/analytics -Dsonar.dynamicAnalysis=reuseReports -Dsonar.java.coveragePlugin=jacoco -Dsonar.jacoco.reportMissing.force.zero=true -Dsonar.java.binaries=/Users/jagadeshmunta/.m2/repository/com/couchbase/analytics

}

run_sca()
{
   ~/sonar-scanner/bin/sonar-scanner -Dsonar.projectKey=analytics   -Dsonar.sources=.   -Dsonar.host.url=http://172.23.105.131:9000   -Dsonar.login=5517d08da769a1fccd8551e6b4431d03baafd005 -Dsonar.java.binaries=$HOME/.m2 -Dsonar.inclusions=**/*.java,**/*.go
  #./sonar-scanner -Dsonar.projectKey=samplejacoco -Dsonar.host.url=http://172.23.105.131:9000 -Dsonar.login=5517d08da769a1fccd8551e6b4431d03baafd005 -Dsonar.coverage.jacoco.xmlReportPaths=/Users/jagadeshmunta/jacocoreports/jacoco.xml -Dsonar.sources=. -Dsonar.inclusions=**/*.java,**/*.go -Dsonar.java.binaries=$HOME/.m2
}

all()
{
    #REPO=$WORKSPACE/.repository
    #REPO=$HOME/.m2
    export WORKSPACE=$HOME
    clean
    repo_sync
    build_analytics $HOME/.m2
}

all

echo "Done!"
