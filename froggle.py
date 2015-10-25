import argparse
import datetime
import json
import os

from freckle_client.client import FreckleClientV2
from toggl.api_client import TogglClientApi

toggl = None
freckle = None

PROJECT_MAP = dict()

FRECKLE_PROJECTS = None


def get_freckle_projects():
    global FRECKLE_PROJECTS
    if FRECKLE_PROJECTS is None:
        FRECKLE_PROJECTS = [(p['id'], p['name']) for p in freckle.fetch_json('projects')]

    return FRECKLE_PROJECTS


def prompt_project_mapping(project_id, project_name):
    # Fetch all Freckle projects
    freckle_projects = get_freckle_projects()
    print "Select Project in Freckle which corresponds to '{} ({})' from Toggl".format(project_name, project_id)
    print
    for i, (id_, name) in enumerate(freckle_projects, 1):
        print "{:2} {}".format(i, name)

    print ' 0: - Skip this project -'

    selected = raw_input('>> ')

    if selected == '0':
        return None

    print "Selected '{}'".format(freckle_projects[int(selected)-1][1])

    return freckle_projects[int(selected)-1][0]


def run(start_date, end_date):
    # 1. Fetch all time entries from Toggl
    time_entries = toggl.query('/time_entries', {'start_date': start_date.isoformat()+'+02:00',
                                                 'end_date': end_date.isoformat()+'+02:00'})

    if time_entries.status_code != 200:
        print time_entries.content
        print time_entries.url
        return

    for entry in time_entries.json():
        # Projectless entries are skipped
        if 'pid' not in entry:
            continue

        # Determine target project
        if entry['pid'] not in PROJECT_MAP:
            # Fetch project info
            project_info = toggl.query('/projects/{}'.format(entry['pid'])).json()['data']
            project_id, project_name = project_info['id'], project_info['name']
            freckle_project_id = prompt_project_mapping(project_id, project_name)
            PROJECT_MAP[project_id] = freckle_project_id

        if PROJECT_MAP[entry['pid']] is None:
            continue

        # Construct request to send to Freckle:
        data = {
            'date': entry['start'].split('T')[0],
            'minutes': entry['duration'] / 60,
            'description': entry['description'] + ' #toggl',
            'project_id': PROJECT_MAP[entry['pid']],
        }
        print data

    print start_date, end_date


def valid_date(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


def load_config():
    filename = os.path.expanduser('~/.froggle')
    if os.path.exists(filename):
        print "Loading tokens from config"
        with open(filename, 'r') as f:
            return json.load(f)


def save_config(config):
    filename = os.path.expanduser('~/.froggle')
    with open(filename, 'w') as f:
        return json.dump(config, f)


if __name__ == '__main__':
    parser = argparse.ArgumentParser('Copy time entries from Toggl to Freckle')
    parser.add_argument('start_date', type=valid_date)
    a = parser.add_argument('--end-date', type=valid_date, default=datetime.datetime.now() - datetime.timedelta(1),
                            required=False)

    parser.add_argument('--freckle-token')
    parser.add_argument('--toggl-token')

    options = parser.parse_args()
    config = load_config() if not options.freckle_token or not options.toggl_token else {}

    if options.freckle_token:
        config['freckle_token'] = options.freckle_token
    if options.toggl_token:
        config['toggl_token'] = options.toggl_token

    global freckle, toggl
    toggl = TogglClientApi({'token': config['toggl_token'], 'user-agent': 'Froggle'})
    freckle = FreckleClientV2(config['freckle_token'])

    save_config(config)

    if options.end_date < options.start_date:
        raise argparse.ArgumentError(a, "Start date should not come after end date")

    run(options.start_date, options.end_date)
