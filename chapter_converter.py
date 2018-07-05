import argparse
import datetime
import re
from os.path import exists, splitext

import chardet


def msToTimestamp(ms):
    ms = int(ms)
    return str(datetime.timedelta(seconds=ms//1000))+'.'+str(ms % 1000)


def timestampToMs(timestamp):
    h, m, s, ms = re.split('[:.]', timestamp)
    return str(1000*(int(h) * 3600 + int(m) * 60 + int(s)) + int(ms))


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("filename")
    parser.add_argument("-f", "--format", default='pot', choices=['simple', 'pot', 'ogm'],
                        help="output format (default: pot)")
    parser.add_argument("-o", "--output", help="output filename")
    args = parser.parse_args()

    if not exists(args.filename):
        print('Input file missing!')
        return 0

    # Detect file encoding
    with open(args.filename, 'rb') as file:
        raw = file.read() 
        encoding = chardet.detect(raw)['encoding']

    # Detect format of input file
    with open(args.filename, encoding=encoding) as f:
        lines = f.readlines()
        # Remove empty lines
        lines = list(filter(lambda x: not re.match(r'^\s*$', x), lines))

        SIMPLE_RE = r"(.+?), *(.+)"
        if re.match(SIMPLE_RE, lines[0]):
            inputFormat = 'simple'
        if re.match(r"CHAPTER\d", lines[0]):
            inputFormat = 'ogm'
        if lines[0].startswith('[Bookmark]'):
            inputFormat = 'pot'

        chapters = []
        if inputFormat == 'simple':
            for line in lines:
                m = re.match(SIMPLE_RE, line)
                if m:
                    chapters.append((m.group(1), m.group(2)))
        if inputFormat == 'ogm':
            for i in range(0, len(lines), 2):
                line1 = lines[i].strip()  # Remove \n at the end
                line2 = lines[i+1].strip()
                chapters.append(
                    (line1[line1.index('=')+1:], line2[line2.index('=')+1:]))
        if inputFormat == 'pot':
            for line in lines[1:]:
                m = re.match(r'\d+=(\d+)\*([^*]+)', line.strip())
                if m:
                    timestamp = msToTimestamp(m.group(1))
                    chapters.append((timestamp, m.group(2)))

    if args.output:
        newFilenme = args.output
    elif args.format == 'pot':
        newFilenme = f'{splitext(args.filename)[0]}.pbf'
    else:
        newFilenme = f'{splitext(args.filename)[0]}.{args.format}.txt'

    # Output
    with open(newFilenme, 'w', encoding='utf-8-sig') as f:
        if args.format == 'simple':
            for time, title in chapters:
                f.write(f'{time},{title}\n')
        if args.format == 'ogm':
            i = 1
            for time, title in chapters:
                f.write(f'CHAPTER{i:02}={time}\n')
                f.write(f'CHAPTER{i:02}NAME={title}\n')
                i += 1
        if args.format == 'pot':
            i = 0
            f.write('[Bookmark]\n')
            for time, title in chapters:
                f.write(f'{i}={timestampToMs(time)}*{title}*\n')
                i += 1


if __name__ == '__main__':
    main()
