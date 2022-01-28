#!/usr/bin/env python3


import sys
import argparse
import json
import tabulate

import config
import utils

# Get aws inventories and write output to result.txt
# inputs: 
#   profile:             profile value in aws config, i.e "cb-qe".
#   service-classes:     a list of aws sdk classes the script is going to check.
#                        a full list is defined in config.py as AWS_CLASSES.keys()
def get_inventories_by_class(profile, service_classes):
    inventory={}
    regions =utils.get_aws_service_regions(profile,'ec2')
    for service_class in service_classes:
        if (service_class == 's3'):
            inventory['s3']=utils.get_s3_inventory(profile)
        else:
            inventory[service_class]=utils.get_inventory_regional(profile, regions, config.AWS_CLASSES[service_class], service_class)
            if 'instance' in inventory[service_class]:
                ec2_events=utils.get_cloudtrail_start_ec2_events(profile, regions)
                for index in range(len(inventory[service_class]['instance'])):
                    if inventory[service_class]['instance'][index]['InstanceId'] in ec2_events:
                        inventory[service_class]['instance'][index]['Last_Username']=ec2_events[inventory[service_class]['instance'][index]['InstanceId']]
                    else:
                        inventory[service_class]['instance'][index]['Last_Username']="Unknown"

                for index in range(len(inventory[service_class]['instance'])):
                    for item in inventory[service_class]['instance'][index]['Tags']:
                        if item['Key'] == "Name":
                            inventory[service_class]['instance'][index]['Instance_Name']=item['Value']
                    for item in inventory[service_class]['instance'][index]['Tags']:
                        if "owner" in item.values():
                            if item['Key'] == "owner":
                                inventory[service_class]['instance'][index]['Cost_Group']=item['Value']
                        else:
                            inventory[service_class]['instance'][index]['Cost_Group']="Unknown"
                    inventory[service_class]['instance'][index].pop('Tags', None)
            #CBD-4534, associate EBS with corresponding EC2.
            #No need to print out the whole attachments information, only EC2 instance id.
            if 'ebs' in inventory[service_class]:
                for index in range(len(inventory[service_class]['ebs'])):
                    if len(inventory[service_class]['ebs'][index]['Attachments']) == 0:
                        inventory[service_class]['ebs'][index]['InstanceId']= None
                    else:
                        inventory[service_class]['ebs'][index]['InstanceId']=inventory[service_class]['ebs'][index]['Attachments'][0]['InstanceId']
                    del inventory[service_class]['ebs'][index]['Attachments']
    with open('result.txt', 'w') as f:
        for service_class in service_classes:
            f.write(f"\n{service_class}:\n")
            for key in inventory[service_class].keys():
                f.write(f"{key}:\n")
                header = inventory[service_class][key][0].keys()
                rows =  [x.values() for x in inventory[service_class][key]]
                f.write(tabulate.tabulate(rows, header))
                f.write(f"\n\n")
    
def parse_args():
    parser = argparse.ArgumentParser(description="Checking current AWS inventories\n\n")
    parser.add_argument('--profile', '-p', help='aws profile', required=True)
    parser.add_argument('--classes', '-c', help='comma separated service classes')
    return parser.parse_args()

def main():
    args = parse_args()
    if args.classes is not None:
        service_classes=list(args.classes.split(","))
    else:
        service_classes=list(config.AWS_CLASSES.keys())
    profile=args.profile
    print(service_classes)

    accountID=utils.get_accountID(profile)
    if(set(service_classes).issubset(config.AWS_CLASSES.keys())):
        get_inventories_by_class(profile, service_classes)
    else:
        print("One or more classes provided, is not supported")
        print(config.AWS_CLASSES.keys())
    

if __name__ == '__main__':
    main()
