#!/bin/bash
##################################################################################################
# Description: Create AWS stack
#
##################################################################################################
COMMAND="$1"
STACK_NAME="$2"
SERVER_COUNT="$3"
SERVER_VERSION="$4"
USER_NAME="$5"
USER_PWD="$6"
TEMPLATE_URL="$7"
if [ "${COMMAND}" = "" ]; then
  echo "Usage: $0 COMMAND STACK_NAME [SERVER_COUNT SERVER_VERSION USER_NAME USER_PWD TEMPLATE_URL]"
  echo "Ex: $0 createstack ${USER}-`date '+%m%d-%H%M%S'`"
  exit 1
fi
: ${SERVER_COUNT:="1"}
: ${SERVER_VERSION:="6.5.1"}
: ${USER_NAME:="Administrator"}
: ${USER_PWD:="password"}
: ${TEMPLATE_URL:="https://awsmp-fulfillment-cf-templates-prod.s3-external-1.amazonaws.com/644f14ea-d766-4f4d-8a93-5a073da68611/fa1fb9f0-2a60-4ed5-a55f-03a28b9f8945.template"}

PARAMS="ParameterKey=InstanceType,ParameterValue=m5.xlarge ParameterKey=KeyName,ParameterValue=couchbase-qe ParameterKey=SSHCIDR,ParameterValue=10.0.0.0/16 ParameterKey=ServerDiskSize,ParameterValue=100 ParameterKey=ServerInstanceCount,ParameterValue=${SERVER_COUNT} ParameterKey=ServerVersion,ParameterValue=${SERVER_VERSION} ParameterKey=SyncGatewayInstanceCount,ParameterValue=0 ParameterKey=SyncGatewayInstanceType,ParameterValue=m5.large ParameterKey=SyncGatewayVersion,ParameterValue=2.7.3 ParameterKey=Username,ParameterValue=${USER_NAME} ParameterKey=Password,ParameterValue=${USER_PWD}"
TAGS="Key=Name,Value=${STACK_NAME}"

createstack()
{
  echo aws cloudformation create-stack --stack-name ${STACK_NAME} --template-url ${TEMPLATE_URL} --parameters ${PARAMS} --tags ${TAGS} --capabilities CAPABILITY_IAM
  aws cloudformation create-stack --stack-name ${STACK_NAME} --template-url ${TEMPLATE_URL} --parameters ${PARAMS} --tags ${TAGS} --capabilities CAPABILITY_IAM
}

deletestack()
{
  echo aws cloudformation delete-stack --stack-name ${STACK_NAME}
  aws cloudformation delete-stack --stack-name ${STACK_NAME}
}

list()
{
  aws cloudformation list-stacks |~/jq '.[][]|(.StackName + " " + .StackStatus)'
}
describe()
{
  aws cloudformation describe-stacks --stack-name ${STACK_NAME}
}

help()
{
  echo createstack : Creates a new aws stack
  echo deletestack : Deletes an existing aws stack
  echo list : List stacks
}

all()
{
  createstack
}

$@
