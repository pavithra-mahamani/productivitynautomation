*** QE Rerun Test jenkins jobs : ***
The goal is to run mainly the jobs with test failures and run only the the failed tests count than 
all tests.

The general configuration should be read from configuration file such as .rerunjobs.ini and 
should work on any dispatcher jobs. Include or exclude the jobs using job path prefix.

- queue of all failed jobs
- queue and trigger per component
- don't run any job that is running
- run only failed jobs - with retry failed only
- checks if at least 10 (configurable) machines available 
- Use the new greenboard eventing document as the source.

Usage:
python3 ~/productivitynautomation/reruns/rerunjobs.py -h

Example:
python3 ~/productivitynautomation/reruns/rerunjobs.py 6.6.0-7675 6.6.0-7675 True mad-hatter


