import sys
import json
import argparse

from random import random
from subprocess import run, CalledProcessError

parser = argparse.ArgumentParser(
    description="""Print iperf3 performance traces to stdout. Arguments other than
    those specified are passed to iperf3.\n\n

    Examples:\n

    Transfer 1MB 10 times: iperf_trace --server 127.0.0.1 --count 10 -n 1MB\n

    Transfer 1MB repeatedly for 5 seconds: iperf_trace --server 127.0.0.1 --time 5 -n 1MB\n
""")
parser.add_argument('--server', type=str, help='Hostname or IP of the iperf3 server.')
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--count', type=int, help='Number of times to run iperf3.')
group.add_argument('--time', type=int, help='Stop after this number of seconds.')
output_group = parser.add_mutually_exclusive_group(required=True)
output_group.add_argument('--json', action='store_true', help='output JSON')
output_group.add_argument('--csv', action='store_true', help='output csv')
parser.add_argument('--write-header', action='store_true', default=False,
                    help='write header to csv file')
parser.add_argument('--minmb', type=float, required=True, help='Minimum number of MBs to send.')
parser.add_argument('--maxmb', type=float, required=True, help='Maximum number of MBs to send.')

def error(msg):
    '''print msg to stderr'''
    if isinstance(msg, bytes):
        msg = msg.decode('ascii')
    sys.stderr.write(msg + '\n')
    sys.stderr.flush()

def check_iperf3():
    '''Raise CalledProcessError if iperf3 isn't installed.'''
    try:
        run(['iperf3', '--version'], check=True, capture_output=True)
    except CalledProcessError as error:
        error('Could not find iperf3: is it installed?')
        sys.exit()
    return

def check_server_reachable(server):
    '''Raise CalledProcessError if the iperf3 server isn't reachable.'''
    try:
        result = run(
            ['timeout', '5', 'iperf3', '-c', server, '-t', '1'],
            capture_output=True,
        )
        result.check_returncode()
    except CalledProcessError as error:
        error(f'iperf3 server on {server} not reachable: is it running?')
        error(result.stdout)
        sys.exit()
    return

def interval_iter(sample):
    '''Iterator over (start_time, duration, bytes) tuples in the intervals in sample'''
    if 'start' not in sample:
        return
    if 'timestamp' not in sample['start']:
        return
    if 'timesecs' not in sample['start']['timestamp']:
        return
    timesecs = sample['start']['timestamp']['timesecs']
    if 'intervals' not in sample:
        return
    for interval in sample['intervals']:
        if 'streams' not in interval:
            continue
        for stream in interval['streams']:
            if 'start' not in stream:
                continue
            if 'bytes' not in stream:
                continue
            if 'seconds' not in stream:
                continue
            yield {
                'timestamp': timesecs+stream['start'],
                'seconds': stream['seconds'],
                'bytes': stream['bytes'],
            }
    return

def iperf(server, MBs):
    '''Run iperf3 in client mode against server with iperf_args and return
    the result as a JSON dict.

    '''
    try:
        args = ['iperf3', '-c', server, '-J', '-n', str(MBs)+'MB']
        result = run(args, capture_output=True)
        result.check_returncode()
        return json.loads(result.stdout)
    except CalledProcessError:
        error('iperf3 failed:')
        error(result.stderr)
        return None

def csv_from_dct(dct, labels=None):
    '''Convert a dict to a csv line'''
    if labels is None:
        labels = dct.keys()
    return ', '.join(str(dct[label]) for label in labels)

def main():
    args = parser.parse_args()
    labels = None
    check_iperf3()
    check_server_reachable(args.server)
    i = 0
    start = 0
    timestamp = 0
    while True:
        if args.count and i >= args.count:
            break
        if args.time and timestamp - start >= args.time:
            break
        i += 1
        MBs = args.minmb + (random() * (args.maxmb - args.minmb))
        dct = iperf(args.server, MBs)
        if not dct:
            continue
        for interval_dct in interval_iter(dct):
            if not interval_dct:
                continue
            timestamp = interval_dct['timestamp']
            if start == 0:
                start = timestamp
            if args.json:
                print(interval_dct)
            elif args.csv:
                if labels is None:
                    labels = list(interval_dct.keys())
                if args.write_header:
                    print(', '.join(str(v) for v in labels))
                    args.write_header = False
                print(csv_from_dct(interval_dct, labels=labels))
        sys.stdout.flush()

if __name__ == '__main__':
    main()
