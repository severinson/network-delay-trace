import sys
import json
import argparse

parser = argparse.ArgumentParser(description='Parse fping output to JSON or CSV')
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--json', action='store_true', help='output JSON')
group.add_argument('--csv', action='store_true', help='output csv')
parser.add_argument('--write-header', action='store_true', default=False,
                    help='write header to csv file')

def error(msg):
    '''print msg to stderr'''
    sys.stderr.write(msg + '\n')
    sys.stderr.flush()

def parse_line(line):
    '''parse one line of fping output'''
    rv = dict()
    header, body = map(str.strip, line.split(':'))

    # parse header
    header_fields = list(map(str.strip, header.split(' ')))
    if len(header_fields) == 1:
        rv['host'], = header_fields
    elif len(header_fields) == 2:
        rv['timestamp'], rv['host'] = header_fields
        rv['timestamp'] = rv['timestamp'].replace('[', '')
        rv['timestamp'] = rv['timestamp'].replace(']', '')
        rv['timestamp'] = float(rv['timestamp'])
    else:
        error(f'Failed to parse\n{line}\n')
        return None

    # parse body
    body, _ = map(str.strip, body.split('('))
    body_fields = list(map(str.strip, body.split(', ')))
    if len(body_fields) != 3:
        error(f'Failed to parse\n{line}\n')
        return None
    rv['seq'], rv['bytes'], rv['ms'] = body_fields
    rv['seq'] = rv['seq'].replace('[', '')
    rv['seq'] = rv['seq'].replace(']', '')
    rv['seq'] = int(rv['seq'])
    rv['bytes'] = int(rv['bytes'].split(' ')[0])
    rv['ms'] = float(rv['ms'].split(' ')[0])
    return rv

def csv_from_dct(dct, labels=None):
    '''Convert a dict to a csv line'''
    if labels is None:
        labels = dct.keys()
    return ', '.join(str(dct[label]) for label in labels)

def main():
    args = parser.parse_args()
    labels = None
    for line in map(str.strip, sys.stdin):
        dct = parse_line(line)
        if not dct:
            continue
        if args.json:
            print(json.dumps(dct))
        elif args.csv:
            if labels is None:
                labels = list(dct.keys())
            if args.write_header:
                print(', '.join(str(v) for v in labels))
                args.write_header = False
            print(csv_from_dct(dct, labels=labels))
        sys.stdout.flush()

if __name__ == '__main__':
    main()
