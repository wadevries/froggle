import argparse
from collections import defaultdict
import datetime
import json
import os

from freckle_client.client import FreckleClientV2
from toggl.api_client import TogglClientApi

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

    print
    print ' 0: - Skip this project -'
    print

    selected = raw_input('>> ')

    if selected == '0':
        return None

    print "Selected '{}'".format(freckle_projects[int(selected)-1][1])

    return freckle_projects[int(selected)-1][0]


def create_freckle_entry(date, project_id, description, minutes):
    data = {
        'date': date,
        'project_id': project_id,
        'description': description + ' #toggl',
        'minutes': minutes,
    }
    return freckle.fetch_json('entries', 'POST', post_args=data)


def run(start_date, end_date):
    collected_entries = defaultdict(int)

    # 1. Fetch all time entries from Toggl
    time_entries = toggl.query('/time_entries', {'start_date': start_date.isoformat()+'+00:00',
                                                 'end_date': end_date.isoformat()+'+00:00'})

    if time_entries.status_code != 200:
        print time_entries.content
        print time_entries.url
        return

    for entry in time_entries.json():
        # Projectless entries are skipped
        if 'pid' not in entry:
            continue

        # Determine target project
        if str(entry['pid']) not in PROJECT_MAP:
            # Fetch project info
            project_info = toggl.query('/projects/{}'.format(entry['pid'])).json()['data']
            project_id, project_name = project_info['id'], project_info['name']
            freckle_project_id = prompt_project_mapping(project_id, project_name)
            PROJECT_MAP[str(project_id)] = freckle_project_id

        if PROJECT_MAP[str(entry['pid'])] is None:
            continue

        # Construct request to send to Freckle:
        collected_entries[(entry['start'].split('T')[0], PROJECT_MAP[str(entry['pid'])], entry['description'])] += entry['duration']

    # Create the "toggl" tag
    print "Creating #toggl tag: {}".format(freckle.fetch_json('tags', 'POST', post_args={'names': ['toggl']}))

    # 5. Create time entries in Freckle
    for ((date, project_id, description), seconds) in sorted(collected_entries.items()):
        minutes = seconds / 60
        response = create_freckle_entry(date, project_id, description, minutes)
        print "Created Freckle entry: {}".format(response)



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
        return json.dump(config, f, indent=4)


def start_of_today():
    return datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser('Copy time entries from Toggl to Freckle')
    parser.add_argument('--start_date', type=valid_date, default=start_of_today() - datetime.timedelta(days=1, microseconds=1))
    a = parser.add_argument('--end-date', type=valid_date, default=start_of_today() - datetime.timedelta(microseconds=1),
                            required=False)

    freckle_token_arg = parser.add_argument('--freckle-token')
    toggl_token_arg = parser.add_argument('--toggl-token')

    options = parser.parse_args()
    config = load_config() if not options.freckle_token or not options.toggl_token else {}

    if (not config or not config.get('freckle_token')) and not options.freckle_token:
        raise argparse.ArgumentError(freckle_token_arg, "No Freckle token provided")
    if options.freckle_token:
        config['freckle_token'] = options.freckle_token
    if (not config or not config.get('toggl_token')) and not options.toggl_token:
        raise argparse.ArgumentError(toggl_token_arg, "No Toggl token provided")
    if options.toggl_token:
        config['toggl_token'] = options.toggl_token

    global freckle, toggl, PROJECT_MAP
    toggl = TogglClientApi({'token': config['toggl_token'], 'user-agent': 'Froggle'})
    freckle = FreckleClientV2(config['freckle_token'])

    PROJECT_MAP = config.get('project_map', {})

    if options.end_date < options.start_date:
        raise argparse.ArgumentError(a, "Start date should not come after end date")

    run(options.start_date, options.end_date)

    config['project_map'] = PROJECT_MAP

    save_config(config)
