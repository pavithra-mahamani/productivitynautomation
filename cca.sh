#!/bin/bash
#####################################################
# Description: Code coverage analysis helper script
#
#####################################################

build_analytics()
{
    echo "*** Building: analytics ***"
    #Pre-build:
    export CB_MAVEN_REPO_LOCAL=$1

    mkdir -p build
    cd build

    cmake -D CB_DOWNLOAD_JAVA=1 -D CB_DOWNLOAD_DEPS=1 ..
    cd ..

    make -j8 || make
    echo ##### end make ####

    mvn -f analytics/cbas/pom.xml -B install -rf :cbas-test -pl :cbas-cbserver-test -am -Drat.skip -Dsource-format.skip -DskipTests -Dfile.encoding=utf-8 -Dmaven.repo.local=$CB_MAVEN_REPO_LOCAL

    echo ##### end test build


    #Build:
    export MAVEN_OPTS=-Xmx4g
    #mvn -f analytics/cbas/pom.xml -B verify -P jenkins,cbas-cbcluster-test -pl :cbas-cbserver-test
    mvn -f analytics/cbas/pom.xml -B verify -P cbas-cbcluster-test -pl :cbas-cbserver-test

    
}

all()
{
    export WORKSPACE=.
    #REPO=$WORKSPACE/.repository
    REPO=$PWD
    build_analytics $REPO
}

all

echo "Done!"
