import datetime
import errno
import fcntl
import json
import os
import shutil
import sys

import py.io
import pytest

def pytest_addoption(parser):
    parser.addoption('--progress', default=None)

session_root = None
root_process = False

def session_path(path):
    return os.path.join(session_root, path)

def create_json_list_file(path, objs=None):
    if objs == None:
        objs = []
    with open(session_path(path), 'w') as f:
        json.dump(objs, f, separators=(',\n', ':'))

def append_to_json_list_file(path, obj):
    with open(session_path(path), 'r+') as f:
        fcntl.lockf(f, fcntl.LOCK_EX)
        f.seek(-1, os.SEEK_END)
        f.write(',\n')
        json.dump(obj, f)
        f.write(']')

def create_index_html():
    template_path = os.path.join(os.path.dirname(__file__), 'index.html')
    #shutil.copyfile(template_path, session_path('index.html'))
    os.symlink(os.path.abspath(template_path), session_path('index.html'))

def force_symlink(source, link_name):
    try:
        os.unlink(link_name)
    except OSError, e:
        if e.errno != errno.ENOENT:
            raise
    os.symlink(source, link_name)

def pytest_configure(config):
    if not config.option.progress:
        return
    global session_root
    global root_process
    session_root = os.environ.get('TESTPROGRESS_SESSION_ROOT')
    if session_root == None:
        root_process = True
        session_dir = str(datetime.datetime.now())
        session_root = os.path.join(config.option.progress, session_dir)
        session_root = os.path.abspath(session_root)
        os.environ['TESTPROGRESS_SESSION_ROOT'] = session_root
        os.mkdir(session_root)
        create_json_list_file('events.json', [None])
        create_index_html()
        force_symlink(session_dir,
                      os.path.join(config.option.progress, 'latest'))
    else:
        root_process = False

def pytest_collection_finish(session):
    if not session.config.option.progress:
        return
    create_json_list_file('collected.json',
                          [{'id': item.nodeid.replace('/', '.')} for item in session.items])

def emit_event(nodeid, when, outcome):
    append_to_json_list_file('events.json',
                             {'id': nodeid.replace('/', '.'),
                              'when': when,
                              'outcome': outcome})

def pytest_runtest_logstart(nodeid, location):
    global session_root
    if session_root != None:
        emit_event(nodeid.replace('/', '.'), 'start', 'passed')

def pytest_runtest_logreport(report):
    global session_root
    if session_root != None and root_process:
        if report.longrepr != None:
            with open(session_path('%s.txt' % report.nodeid.replace('/', '.')), 'a') as f:
                header = '%s %s %s' % (report.nodeid, report.when, report.outcome)
                f.write('%s\n' % ('X' * len(header)))
                f.write('%s\n' % header)
                f.write('%s\n' % ('v' * len(header)))
                report.toterminal(py.io.TerminalWriter(f))
        emit_event(report.nodeid.replace('/', '.'), report.when, report.outcome)

orig_fds = None

@pytest.mark.tryfirst
def pytest_runtest_setup(item):
    global session_root
    if session_root == None:
        return

    sys.stdout.flush()
    sys.stderr.flush()

    global orig_fds
    assert orig_fds == None
    orig_fds = (os.dup(0), os.dup(1), os.dup(2))

    in_fd = os.open('/dev/null', os.O_RDONLY)
    os.dup2(in_fd, 0)
    os.close(in_fd)

    out_fd = os.open(session_path('%s.txt' % item.nodeid.replace('/', '.')),
                     os.O_CREAT | os.O_EXCL | os.O_APPEND | os.O_WRONLY)
    os.dup2(out_fd, 1)
    os.dup2(out_fd, 2)
    os.close(out_fd)

@pytest.mark.tryfirst
def pytest_runtest_teardown(item):
    global session_root
    if session_root == None:
        return

    sys.stdout.flush()
    sys.stderr.flush()
    global orig_fds
    for fd in (0, 1, 2):
        os.dup2(orig_fds[fd], fd)
        os.close(orig_fds[fd])
    orig_fds = None

def pytest_sessionfinish(session, exitstatus):
    global session_root
    if session_root == None:
        return

    global root_process
    if root_process:
        append_to_json_list_file('events.json', 'done');
