#!/usr/bin/env python
import argparse, base64, calendar, httplib, json, re, subprocess, sys, time

def error(s):
    print 'error:', s
    sys.exit(1)

def set_commit_success(user, password, repo, commit):
    conn = httplib.HTTPSConnection('api.github.com')

    body = json.dumps({'state': 'success',
                       'target_url': 'http://whatever.com',
                       'description': 'LLVM sanity check passed',
                       'context': 'sanity-check'})

    auth_token = base64.encodestring('%s:%s' % (user, password))[:-1]
    headers = {'Content-Type': 'application/json',
               'Authorization': 'Basic %s' % auth_token,
               'User-Agent': 'llvm-sanity-check'}

    conn.request('POST', '/repos/%s/%s/statuses/%s' % (user, repo, commit),
                 body, headers)
    resp = conn.getresponse()
    if resp.status != 201:
        error('GitHub API request failed with status %d' % resp.status)

    conn.close()

def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True).strip()
    except subprocess.CalledProcessError as e:
        error(e.message)

def get_config(name):
    return run('git config %s' % name)

def infer_repo():
    # FIXME: should be current tracking repo's url?
    url = get_config('remote.llvm.url')
    if not url:
        error('"llvm" remote not found, please create it')
    m = re.search(r'/([^/]+)\.git', url)
    if not m:
        error('"llvm" remote pointing to unknown location')
    return m.group(1)

def infer_branch():
    return run('git rev-parse --abbrev-ref HEAD')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--branch')
    args = parser.parse_args()

    if args.branch:
        branch = args.branch
    else:
        branch = infer_branch()

    merges = run('git rev-list --merges llvm/%s..HEAD' % branch)
    if len(merges) != 0:
        error('update includes merge commits')

    # 3. Check timestamps between origin/master and commits are monotonic.
    #     'git log upstream..master --format=format:%ct' and check decreasing.
    commit_times = run('git log --format="%%ct" llvm/%s^..HEAD' % branch)
    commit_times = list(reversed(map(int, commit_times.split())))

    if sorted(commit_times) != commit_times:
        error('commit dates not monotonic, consider running "git rebase -f"')

    # 4. Check timestamp is not in the future.
    #     Check above against canonical time.
    # FIXME: use an internet server for correct time
    if commit_times[-1] > calendar.timegm(time.gmtime()):
        error('HEAD is from the future')

    # All checks have passed
    # 2. Infer repository
    repo = infer_repo()

    # 6. Infer user and password
    user = get_config('llvm.user')
    token = get_config('llvm.token')

    # 7. Update success status.
    commit = run('git rev-parse HEAD')
    print 'Running success: %s, %s, %s, %s' % (user, token, repo, commit)
    set_commit_success(user, token, repo, commit)

    pass

if __name__ == '__main__':
    main()
