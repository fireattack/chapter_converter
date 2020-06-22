from subprocess import run
import argparse
import datetime
import re
from os.path import exists, splitext
from os import remove
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

def load_file_content(filename):
        # Detect file encoding
        with open(filename, 'rb') as file:
            raw = file.read() 
            encoding = chardet.detect(raw)['encoding']

        # Detect format of input file
        with open(filename, encoding=encoding) as f:
            return f.readlines()

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("filename", nargs='?', help="input filename")
    parser.add_argument("-f", "--format", choices=['simple', 'pot', 'ogm', 'tab','xml'], help="output format (default: pot)")
    parser.add_argument("--mp4-charset", help="input chapter charset for mp4 file, since it can't be auto detected (default: utf-8)", default='utf-8')
    parser.add_argument("--charset", help="output file charset (default: utf-8-sig)", default='utf-8-sig')
    parser.add_argument("-o", "--output", help="output filename (default: original_filename.format[.txt])")
    parser.add_argument('-c', '--clipboard', action='store_true', help='automatically process text in clipboard and save it back.')
    args = parser.parse_args()

    # Input handling
    if args.filename and exists(args.filename):
        if args.filename.lower().endswith('.xml'):
            run(['mkvmerge', '-o', 'temp.mks', '--chapters', args.filename])
            run(['mkvextract', 'temp.mks', 'chapters', '-s', 'temp.ogm.txt'])
            lines = load_file_content('temp.ogm.txt')
            remove('temp.mks')
            remove('temp.ogm.txt')
        elif args.filename.lower().split('.')[-1] in ['mp4','mkv']:
            run(['mkvmerge', '-o', 'temp.mks', '-A', '-D', '--chapter-charset', args.mp4_charset, args.filename])
            run(['mkvextract', 'temp.mks', 'chapters', '-s', 'temp.ogm.txt'])
            lines = load_file_content('temp.ogm.txt')
            remove('temp.mks')
            remove('temp.ogm.txt')
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

    # Remove empty lines
    lines = list(filter(lambda x: not re.match(r'^\s*$', x), lines))
    input_format = ''
    SIMPLE_RE = r"([0-9:.]+?), *(.+)"
    TAB_RE = r"([0-9:.].+?)\t(.+)"
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
    
    # Input text parsing
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

    # Set default output format if not specified. 
    if not args.format:
        args.format = 'pot' # Default to pot
        if args.clipboard and input_format != 'tab': 
            args.format = 'tab' # Default to "tab" if get from clipboard for spreadsheet editing.
        if args.output: # Get output format from output filename, if speicified. 
            ext = splitext(args.output)[-1]
            if ext.lower() == '.pbf':
                args.format = 'pot'
            elif ext.lower() == '.xml':
                args.format = 'xml'
            elif ext.lower() == '.txt':
                args.format = 'ogm'

    # Output filename handling
    if args.clipboard and not args.output:
        pass
    else:
        if args.output:
            new_filename = args.output
            args.clipboard = False
        else:
            if args.format == 'pot':
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

    # Genreate output text
    output = ''
    if args.format == 'tab':
        for time, title in chapters:
            output = output + f'{time}\t{title}\n'
    elif args.format == 'simple':
        for time, title in chapters:
            output = output + f'{time},{title}\n'
    elif args.format in ['ogm','xml']:
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
        print('Set data to clipboard:')
        print(output)
        set_clipboard_data(output.replace('\n','\r\n'))
    elif args.format == 'xml':
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
