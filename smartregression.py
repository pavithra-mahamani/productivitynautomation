from github import Github
from pprint import pprint
import os
import urllib2
import logging
import sys
from optparse import OptionParser
import re

log = logging.getLogger(__name__)
logging.info(__name__)
pprint("*** Smart Regression from Changelog ***")

def usage(err=None):
    print("""\
Syntax: smartregression.py options

Examples:
 python smartregression.py -f '6.5.0-4959' -t '6.5.0-4960'
""")
    sys.exit(0)

changelog_rx_dict = {
    'changelog': re.compile(r'CHANGELOG for (?P<changelog>.*)\n'),
    'commit': re.compile(r' * Commit: <a href=\'(?P<commit>.*)\'>'),
}

git_access_token=""
def parse_args(argv):
    parser = OptionParser()
    parser.add_option("-f", "--from", dest="fromb", help="From build id, e.g: -f 6.5.0-4959")
    parser.add_option("-t", "--to", dest="tob", help="To build id, e.g: -t 6.5.0-4960")
    parser.add_option("-p", "--product", dest="product", help="Product e.g: -p couchbase-server",
                      default="couchbase-server")
    parser.add_option("-c", "--changelog_server_url", dest="changelog_server_url",
                      help="Changelog server url, e.g:",
                      default="http://172.23.123.43:8000/getchangelog")
    parser.add_option("-a", "--git_access_token", dest="git_access_token", help="Git user access "
                                                                                "token")
    parser.add_option("-r", "--repos_list", action="store_true", help="To print all repos")
    parser.add_option("-l", "--log-level", dest="loglevel", default="INFO",
                      help="e.g -l info,warning,error")
    options, args = parser.parse_args()

    setLogLevel(options.loglevel)

    if not options.fromb or not options.tob:
        parser.error("Please specify -f <frombuild> and -t <tobuild> options.")
        parser.print_help()

    return options


def setLogLevel(log_level):
    if log_level and log_level.lower() == 'info':
        log.setLevel(logging.INFO)
    elif log_level and log_level.lower() == 'warning':
        log.setLevel(logging.WARNING)
    elif log_level and log_level.lower() == 'debug':
        log.setLevel(logging.DEBUG)
    elif log_level and log_level.lower() == 'critical':
        log.setLevel(logging.CRITICAL)
    elif log_level and log_level.lower() == 'fatal':
        log.setLevel(logging.FATAL)
    else:
        log.setLevel(logging.NOTSET)


# Get change log
def get_change_log(git, changelog_server_url, prod, fromb, tob):
    url_path = changelog_server_url + "?product="+prod+"&fromb="+fromb+"&tob="+tob
    if not os.path.exists('logs'):
        os.mkdir('logs')
    filepath = 'logs'+''.join(os.sep)+'changelog_'+fromb+'_'+tob+".txt"
    log.info("Downloading " + url_path +" to "+filepath)
    try:
        filedata = urllib2.urlopen(url_path)
        datatowrite = filedata.read()
        with open(filepath, 'wb') as f:
            f.write(datatowrite)
    except Exception as ex:
        log.error("Error:: "+str(ex)+"! Please check if " + url_path + " URL is accessible!! "
                                                                    "Exiting...")
        sys.exit(1)
    log.info("Loading change data from "+filepath)

    data, new_data = parse_changelog_file(filepath)
    #log.info(new_data)
    #print("\nTotal number of commits: "+str(len(data)))
    comps = new_data.keys()
    all_commits_count = 0
    comp_index=0
    for comp in comps:
        comp_index +=1
        comp_commits = 0
        print("\n "+str(comp_index)+"."+comp)
        for commit in new_data[comp]:
            git_commit_parts = commit.split("/")
            commit_id = git_commit_parts[-1]
            product_id = git_commit_parts[-4]
            comp_id = git_commit_parts[-3]
            repo_id = product_id + "/" + comp_id
            log.info(repo_id + "," + commit_id)
            comp_commits += 1
            if git:
                get_commit(git, repo_id, commit_id)
        all_commits_count += comp_commits
        print(str(comp_id) + ": total commits=" + str(comp_commits))

    print("\nTotal number of commits: " + str(all_commits_count))
    print("Total number of components: "+ str(len(comps))+" and list is "+str(comps))


def parse_changelog_line(line):
    for key, rx in changelog_rx_dict.items():
        match = rx.search(line)
        if match:
            return key, match

    return None, None

def parse_changelog_file(filepath):
    data = []
    new_data = {}
    changelog = ''
    prev_changelog = ''
    with open(filepath, 'r') as file_object:
        line = file_object.readline()
        comp_count = 0
        comp_commits = 0
        commits = []
        while line:
            key, match = parse_changelog_line(line)
            if  key == 'changelog':
                prev_changelog = changelog
                changelog = match.group('changelog')
                if changelog != 'testrunner' and changelog != 'build':
                    comp_count += 1
                    if comp_commits != 0:
                        new_data[prev_changelog] = commits
                        commits = []
                        comp_commits = 0

            if changelog != 'testrunner' and changelog != 'build' and key == 'commit':
            #if key == 'commit':
                commit = match.group('commit')
                #log.info(commit)
                comp_commits += 1
                row = {
                    'Changelog': changelog,
                    'Commit': commit
                }
                commits.append(commit)
                data.append(row)

            line = file_object.readline()
        if comp_commits != 0:
            new_data[prev_changelog] = commits

    return data, new_data

def print_all_repos(git):
    rindex = 1
    for repo in git.get_user().get_repos():
        log.info( str(rindex) +". " + repo.name)
        rindex = rindex+1

def get_commit(git, repo, sha):
    repo = git.get_repo(repo)
    commit = repo.get_commit(sha=sha)
    log.info(str(commit.commit.author.date)+ " " + commit.commit.author.name + " "
    + commit.commit.author.email +" "+ commit.commit.url +" "+commit.commit.message)

    #tree = commit.commit.tree
    #for treelement in tree.tree:
    #    print(treelement)
    #print(tree)


def main():
    options = parse_args(sys.argv)
    git=''
    if options.git_access_token:
        git = Github(options.git_access_token)
    if options.repos_list:
        print_all_repos(git)
    else:
        get_change_log(git, options.changelog_server_url, options.product, options.fromb,
                           options.tob)


if __name__ == "__main__":
    main()