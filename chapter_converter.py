import argparse
import datetime
import re
from os.path import exists, splitext
import win32clipboard

import chardet

def get_clipboard_data():
    win32clipboard.OpenClipboard()
    data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    return data

def set_clipboard_data(data):
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(data, win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()

def ms_to_timestamp(ms):
    ms = int(ms)
    return str(datetime.timedelta(seconds=ms//1000))+'.'+str(ms % 1000)


def timestamp_to_ms(timestamp):
    h, m, s, ms = re.split('[:.]', timestamp)
    return str(1000*(int(h) * 3600 + int(m) * 60 + int(s)) + int(ms))


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("filename", nargs='?')
    parser.add_argument("-f", "--format", default='pot', choices=['simple', 'pot', 'ogm', 'tab'],
                        help="output format (default: pot)")
    parser.add_argument("-o", "--output", help="output filename (default: original_filename.format[.txt])")
    parser.add_argument('-c', '--clipboard', action='store_true', help='Automatically process text in clipboard.')
    args = parser.parse_args()

    # Input handling
    if args.clipboard:
        f = get_clipboard_data()
        if f:
            print('Get data from clipboard:')
            print(f)
            lines = f.splitlines()
        else:
            print('No valid data in clipboard!')
            return 0
    else:
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
    TAB_RE = r"(.+?)\t(.+)"
    if re.match(SIMPLE_RE, lines[0]):
        input_format = 'simple'
    elif re.match(TAB_RE, lines[0]):
        input_format = 'tab'
    elif re.match(r"CHAPTER\d", lines[0]):
        input_format = 'ogm'
    elif lines[0].startswith('[Bookmark]'):
        input_format = 'pot'
    if not input_format:
        print('Can\'t guess file format!')
        return 0
        
    chapters = []
    if input_format == 'simple':
        for line in lines:
            m = re.match(SIMPLE_RE, line)
            if m:
                chapters.append((m.group(1), m.group(2)))
    elif input_format == 'tab':
        for line in lines:
            m = re.match(TAB_RE, line)
            if m:
                chapters.append((m.group(1), m.group(2)))
    elif input_format == 'ogm':
        for i in range(0, len(lines), 2):
            line1 = lines[i].strip()  # Remove \n at the end
            line2 = lines[i+1].strip()
            chapters.append(
                (line1[line1.index('=')+1:], line2[line2.index('=')+1:]))
    elif input_format == 'pot':
        for line in lines[1:]:
            m = re.match(r'\d+=(\d+)\*([^*]+)', line.strip())
            if m:
                timestamp = ms_to_timestamp(m.group(1))
                chapters.append((timestamp, m.group(2)))
    
    #Output filename handling
    if not args.clipboard:
        if args.output:
            new_filename = args.output
        elif args.format == 'pot':
            new_filename = f'{splitext(args.filename)[0]}.pbf'
            if new_filename == args.filename:
                new_filename = f'{splitext(args.filename)[0]} (2).pbf'
        else:
            new_filename = f'{splitext(args.filename)[0]}.{args.format}.txt'
    
    if args.clipboard and input_format == 'ogm':
        args.format = 'tab'
    if args.clipboard and input_format == 'tab':
        args.format = 'ogm'

    output = ''
    if args.format == 'tab':
        for time, title in chapters:
            output = output + f'{time}\t{title}\n'
    elif args.format == 'simple':
        for time, title in chapters:
            output = output + f'{time},{title}\n'
    elif args.format == 'ogm':
        i = 1
        for time, title in chapters:
            output = output + f'CHAPTER{i:02}={time}\n'
            output = output + f'CHAPTER{i:02}NAME={title}\n'
            i += 1
    elif args.format == 'pot':
        i = 0
        output = output + '[Bookmark]\n'
        for time, title in chapters:
            output = output + f'{i}={timestamp_to_ms(time)}*{title}*\n'
            i += 1

    # Output to clipboard/file                
    if args.clipboard:
        set_clipboard_data(output)
        print('Set data to clipboard:')
        print(output)
    else:
        with open(new_filename, 'w', encoding='utf-8-sig') as f:
            f.write(output)


if __name__ == '__main__':
    main()
