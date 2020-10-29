import jenkinshelper
import traceback
from datetime import datetime
import pytz
from pytz import timezone
import requests


def get_hanging_jobs(jenkins_server_url):
    server = jenkinshelper.connect_to_jenkins(jenkins_server_url)
    running_builds = server.get_running_builds()

    for build in running_builds:
        try:
            latest_timestamp = None
            console = requests.get(
                build['url'] + 'consoleText').iter_lines(decode_unicode=True)
            for line in console:

                def parse_timestamp(timestamp, format):
                    timestamp = datetime.strptime(timestamp, format)
                    timestamp = timezone("US/Pacific").localize(timestamp).astimezone()
                    return timestamp

                try:
                    # new_install.py format
                    split = line.split(" ")
                    day = split[0]
                    time = split[1].split(",")[0]
                    latest_timestamp = parse_timestamp(day + " " + time, "%Y-%m-%d %H:%M:%S")
                    continue
                except Exception:
                    pass

                try:
                    split = line.split(" ")
                    day = split[0].split("[")[1]
                    time = split[1].split("]")[0].split(",")[0]
                    latest_timestamp = parse_timestamp(day + " " + time, "%Y-%m-%d %H:%M:%S")
                    continue
                except Exception:
                    pass

                try:
                    # [2020-10-28T23:36:38-07:00, sequoiatools/cmd:825833] 300

                    timestamp = line.split(" ")[0].split("[")[1][:19]
                    latest_timestamp = parse_timestamp(timestamp, "%Y-%m-%dT%H:%M:%S")
                    continue
                except Exception:
                    pass

            if latest_timestamp:
                
                now = datetime.now().astimezone()
                difference = (now - latest_timestamp).total_seconds() / 60

                # 1 hour
                if difference >= 60:
                    print("{0} is hanging (last console output: {1} ({2:2.2f} minutes ago)".format(build['url'], latest_timestamp, difference))

            else:

                print("timestamp not found for ", build['url'])
            
        except Exception as e:
            traceback.print_exc()
            pass

if __name__ == "__main__":
    get_hanging_jobs("http://qa.sc.couchbase.com")
