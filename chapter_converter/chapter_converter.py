import argparse
import datetime
import re
from os import remove
from os.path import exists, splitext
from subprocess import run

import chardet
import pyperclip


def get_clipboard_data():
    return pyperclip.paste()


def set_clipboard_data(data: str):
    pyperclip.copy(data)


def ms_to_timestamp(ms_str: str):
    ms = int(ms_str)
    return f'{datetime.timedelta(seconds=ms//1000)}.{ms % 1000:03d}'


def timestamp_to_ms(timestamp: str):
    '''acceptable timestamp format: [00:]00:00[.000]'''
    if timestamp.count(':') == 1:
        timestamp = f'00:{timestamp}'
    if '.' not in timestamp:
        timestamp += '.000'
    h, m, s, ms = re.split('[:.]', timestamp)
    ms = ms.ljust(3, '0')[:3]
    return str(1000 * (int(h) * 3600 + int(m) * 60 + int(s)) + int(ms))


def load_file_content(filename: str):
    # Detect file encoding
    with open(filename, 'rb') as file:
        raw = file.read()
        encoding = chardet.detect(raw)['encoding']
    # Detect format of input file
    with open(filename, encoding=encoding) as f:
        return f.readlines()


def extract_and_read_chapters():
    run(['mkvextract', 'temp.mks', 'chapters', '-s', 'temp.ogm.txt'])
    result = load_file_content('temp.ogm.txt')
    remove('temp.mks')
    remove('temp.ogm.txt')
    return result


def get_output_filename(args: argparse.Namespace):
    if args.output:
        new_filename = args.output
        assert isinstance(new_filename, str) # For type checking
    elif args.format == 'pot':
        new_filename = f'{splitext(args.filename)[0]}.pbf'
    elif args.format == 'xml':
        new_filename = f'{splitext(args.filename)[0]}.xml'
    else:
        new_filename = f'{splitext(args.filename)[0]}.{args.format}.txt'
    # Ensure to not override existing file(s)
    i = 2
    stem = splitext(new_filename)[0]
    ext = splitext(new_filename)[1]
    while exists(new_filename):
        new_filename = f'{stem} ({i}){ext}'
        i += 1
    return new_filename


def args_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", nargs='?', help="input filename")
    parser.add_argument("-f", "--format", choices=['simple', 'pot', 'ogm', 'tab', 'xml'], help="output format (default: pot)")
    parser.add_argument("--mp4-charset", default='utf-8', help="input chapter charset for mp4 file, since it can't be auto detected (default: utf-8)")
    parser.add_argument("--charset", default='utf-8-sig', help="output file charset (default: utf-8-sig)")
    parser.add_argument("-o", "--output", help="output filename (default: original_filename.format[.txt])")
    parser.add_argument('-c', '--clipboard', action='store_true', help='automatically process text in clipboard and save it back.')
    return parser


def main(*paras):
    parser = args_parser()
    if paras:
        paras = list(map(str, paras))
        args = parser.parse_args(paras)
    else:
        args = parser.parse_args()

    # Input handling, get lines
    if args.filename and exists(args.filename):
        lower_ext = splitext(args.filename)[1].lower()
        if lower_ext == '.xml':
            run(['mkvmerge', '-o', 'temp.mks', '--chapters', args.filename])
            lines = extract_and_read_chapters()
        elif lower_ext in ['.mp4', '.mkv']:
            run(['mkvmerge', '-o', 'temp.mks', '-A', '-D', '--chapter-charset', args.mp4_charset, args.filename])
            lines = extract_and_read_chapters()
        else:
            lines = load_file_content(args.filename)
    elif args.clipboard:
        f = get_clipboard_data()
        if f:
            print('Get data from clipboard:')
            print(f)
            lines = f.splitlines()
        else:
            print('No valid input data in clipboard!')
            return 0
    else:
        print('Input file missing or invalid!')
        return 0
    # Strip every line and remove empty lines
    lines = [line.strip() for line in lines if line.strip()]

    # Detect input format
    input_format = ''
    MEDIAINFO_RE = r"([0-9:.]+?)\s+:\s[a-z]{0,2}:(.+)"
    HUMAN_RE = r"(?P<time>\d+:\d{1,2}[0-9:.]*)(,?\s*)(?P<name>.+)"
    if re.match(HUMAN_RE, lines[0]):
        input_format = 'human'
    elif re.match(r"CHAPTER\d", lines[0]):
        input_format = 'ogm'
    elif lines[0].startswith('[Bookmark]'):
        input_format = 'pot'
    elif lines[0].startswith('Menu') and re.match(MEDIAINFO_RE, lines[1]):
        lines = lines[1:]
        input_format = 'mediainfo'
    elif re.match(MEDIAINFO_RE, lines[0]):
        input_format = 'mediainfo'
    if not input_format:
        print("Can't guess file format!")
        return 0

    # Input text parsing
    chapters = []
    if input_format == 'human':
        for line in lines:
            m = re.match(HUMAN_RE, line)
            if m:
                timestamp = ms_to_timestamp(timestamp_to_ms(m['time'])) # normalize timestamp
                name = m['name']
                chapters.append((timestamp, name))
    elif input_format == 'ogm':
        chapters = [(lines[i].split('=')[1], lines[i + 1].split('=')[1])
                    for i in range(0, len(lines), 2)]
    elif input_format == 'pot':
        for line in lines[1:]:
            m = re.match(r'\d+=(\d+)\*([^*]+)', line)
            if m:
                timestamp = ms_to_timestamp(m[1])
                chapters.append((timestamp, m[2]))
    elif input_format == 'mediainfo':
        for line in lines:
            m = re.match(MEDIAINFO_RE, line)
            if m:
                chapters.append((m[1], m[2]))

    # Set default output format if not specified.
    if not args.format:
        args.format = 'pot' # Default to pot
        if args.clipboard:
            args.format = 'tab' # Default to "tab" if getting from clipboard for spreadsheet editing.
        if args.output: # Get output format from output filename, if specified.
            lower_ext = splitext(args.output)[-1].lower()
            if lower_ext == '.pbf':
                args.format = 'pot'
            elif lower_ext == '.xml':
                args.format = 'xml'
            elif lower_ext == '.txt':
                args.format = 'ogm'

    # Generate output text
    output = ''
    if args.format == 'tab':
        for time, title in chapters:
            output += f'{time}\t{title}\n'
    elif args.format == 'simple':
        for time, title in chapters:
            output += f'{time},{title}\n'
    elif args.format in ['ogm', 'xml']:
        for i, (time, title) in enumerate(chapters, start=1):
            output += f'CHAPTER{i:02}={time}\n'
            output += f'CHAPTER{i:02}NAME={title}\n'
    elif args.format == 'pot':
        output += '[Bookmark]\n'
        for i, (time, title) in enumerate(chapters):
            output += f'{i}={timestamp_to_ms(time)}*{title}*\n'

    # Output to clipboard if no output is specified
    if args.clipboard and not args.output:
        print('Set data to clipboard:')
        print(output)
        set_clipboard_data(output.replace('\n', '\r\n'))
    # Output to file iff output filename is specified or not clipboard mode.
    else:
        new_filename = get_output_filename(args)
        print(f'Write to file: {new_filename}')
        if args.format == 'xml':
            with open('temp.ogm.txt', 'w', encoding=args.charset) as f:
                f.write(output)
            run(['mkvmerge', '-o', 'temp.mks', '--chapters', 'temp.ogm.txt'])
            run(['mkvextract', 'temp.mks', 'chapters', new_filename])
            remove('temp.mks')
            remove('temp.ogm.txt')
        else:
            with open(new_filename, 'w', encoding=args.charset) as f:
                f.write(output)


if __name__ == '__main__':
    main()
