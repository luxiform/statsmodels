"""
Generate a release note template.  The key parameters are
RELEASE, VERSION, MILESTONE BRANCH, and LAST_COMMIT_SHA.

LAST_COMMIT_SHA is the sha of the commit used to produce the previous
version. This is used to determine the time stamp where commits in the
current release begin.

Requires PyGitHub, dateparser and jinja2
"""

import datetime as dt
import os
from collections import defaultdict

import dateparser
from github import Github
from jinja2 import Template

# Full release version
RELEASE = "0.11.0"
# The current milestone and short version
VERSION = MILESTONE = "0.11"
# This is the final commit from the previous release
LAST_COMMIT_SHA = "8e58e465159f26716b2b9a1396a8763c88579725"
# Branch, usually master but can be a maintenance branch as well
BRANCH = "master"
ACCESS_TOKEN = os.environ.get("GITHUB_ACCESS_TOKEN", None)
if not ACCESS_TOKEN:
    raise RuntimeError("Must set environment variable GITHUB_ACCESS_TOKEN "
                       "containing a valid GitHub access token before running"
                       "this program.")

# Using an access token
g = Github(ACCESS_TOKEN)
# Get the repo
statsmodels = g.get_user("statsmodels").get_repo("statsmodels")
# Look up the modification time of the commit used to tag the previous release
last_modified = statsmodels.get_commit(LAST_COMMIT_SHA).commit.last_modified
last_modified = dateparser.parse(last_modified)
# Look for times creater than this time plus 1 second
first_commit_time = last_modified + dt.timedelta(seconds=1)
first_commit_time_iso = first_commit_time.isoformat()

# General search for sm/sm, PR, merged, merged> first commit time and branch
query_parts = ("repo:statsmodels/statsmodels",
               "is:pr",
               "is:merged",
               "merged:>{}".format(first_commit_time_iso),
               "base:{}".format(BRANCH))
query = " ".join(query_parts)
merged_pull_data = []
merged_pulls = g.search_issues(query)
for pull in merged_pulls:
    merged_pull_data.append({"number": pull.number,
                             "title": pull.title,
                             "login": pull.user.login}
                            )
merged_pull_data = sorted(merged_pull_data, key=lambda x: x["number"])

# Robust name resolutions using commits and GitHub lookup
names = defaultdict(set)
extra_names = set()
for pull in merged_pull_data:
    print("Reading commit data for PR#{}".format(pull['number']))
    pr = statsmodels.get_pull(pull["number"])
    for commit in pr.get_commits():
        name = commit.commit.author.name
        if name and commit.author:
            names[commit.author.login].update([name])
        elif name:
            extra_names.update([name])

for login in names:
    user = g.get_user(login)
    if user.name:
        names[login].update([user.name])

contributors = []
for login in names:
    print("Reading user data for {}".format(login))
    user_names = list(names[login])
    if len(user_names) == 1:
        name = user_names[0]
        if " " in name:
            name = name.title()
        contributors.append(name)
    else:
        valid = [name for name in user_names if " " in name]
        if len(valid) == 0:
            contributors.append(login)
        else:
            contributors.append(valid[0].title())

contributors = sorted(set(contributors))

query_parts = ("repo:statsmodels/statsmodels",
               "is:issue",
               "is:closed",
               "closed:>{}".format(first_commit_time_iso))
query = " ".join(query_parts)
closed_issues = g.search_issues(query)
issues_closed = closed_issues.totalCount

# Variables for the template
variables = {"milestone": MILESTONE,
             "release": RELEASE,
             "version": VERSION,
             "issues_closed": issues_closed,
             "pulls_merged": len(merged_pull_data),
             "contributors": contributors,
             "pulls": merged_pull_data
             }
# Read the template and generate the output
with open("release_note.tmpl", encoding="utf-8") as tmpl:
    tmpl_data = tmpl.read()
    t = Template(tmpl_data)
    rendered = t.render(**variables)
    file_name = "version{}.rst".format(VERSION)
    with open(file_name, encoding="utf-8", mode="w") as out:
        out.write(rendered)
