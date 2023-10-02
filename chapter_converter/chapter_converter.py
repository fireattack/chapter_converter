import argparse
import datetime
import re
from subprocess import run
from pathlib import Path


import chardet
import pyperclip


def ensure_nonexist(f):
    f = Path(f)
    i = 2
    stem = f.stem
    if m:= re.search(r'^(.+?)_(\d)$', stem):
        stem = m[1]
        i = int(m[2]) + 1
    while f.exists():
        f = f.with_name(f'{stem}_{i}{f.suffix}')
        i = i + 1
    return f

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


def load_file_content(filename):
    filename = Path(filename)
    # Detect file encoding
    with filename.open('rb') as file:
        raw = file.read()
        encoding = chardet.detect(raw)['encoding']
    # Detect format of input file
    with filename.open('r', encoding=encoding) as f:
        return f.readlines()


def extract_and_read_chapters(mks_file):
    temp_ogm_txt = ensure_nonexist('temp.ogm.txt')
    run(['mkvextract', mks_file, 'chapters', '--simple', temp_ogm_txt])
    result = load_file_content(temp_ogm_txt)
    mks_file.unlink()
    temp_ogm_txt.unlink()
    return result


def get_output_file(args: argparse.Namespace):
    if args.output:
        output_file = Path(args.output)
    else:
        f = Path(args.filename)
        if args.format == 'pot':
            output_file = f.with_suffix('.pbf')
        elif args.format == 'xml':
            output_file = f.with_suffix('.xml')
        else:
            output_file = f.with_suffix(f'.{args.format}.txt')
    if args.yes:
        if output_file.exists():
            print(f'{output_file} already exists, will overwrite it.')
        return output_file
    else:
        return ensure_nonexist(output_file)


def args_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", nargs='?', help="input filename")
    parser.add_argument("-f", "--format", choices=['simple', 'pot', 'ogm', 'tab', 'xml'], help="output format (default: pot)")
    parser.add_argument("--mp4-charset", default='utf-8', help="input chapter charset for mp4 file, since it can't be auto detected (default: utf-8)")
    parser.add_argument("--charset", default='utf-8-sig', help="output file charset. XML output will always be utf-8-sig (default: utf-8-sig)")
    parser.add_argument("-o", "--output", help="output filename (default: original_filename.format[.txt])")
    parser.add_argument('-c', '--clipboard', action='store_true', help='automatically process text in clipboard and save it back.')
    parser.add_argument('--lang', help='manually set language tag for XML chapter.')
    parser.add_argument('--yes', '-y', action='store_true', help='automatically overwrite existing file.')
    return parser


def main(*paras):
    parser = args_parser()
    if paras:
        paras = list(map(str, paras))
        args = parser.parse_args(paras)
    else:
        args = parser.parse_args()

    # Input handling
    if args.filename:
        f = Path(args.filename)
        if not f.exists():
            print('Input file not exists!')
            return 0
        lower_ext = f.suffix.lower()
        if lower_ext == '.xml':
            mks_file = ensure_nonexist('temp.mks')
            run(['mkvmerge', '-o', mks_file, '--chapters', args.filename])
            lines = extract_and_read_chapters(mks_file)
        elif lower_ext in ['.mp4', '.mkv']:
            mks_file = ensure_nonexist('temp.mks')
            run(['mkvmerge', '-o', mks_file, '-A', '-D', '--chapter-charset', args.mp4_charset, args.filename])
            lines = extract_and_read_chapters(mks_file)
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
    MEDIAINFO_RE = r"([0-9:.]+?)\s+:\s([a-z]{0,2}):(.+)"
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
    lang_tags = []

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
                chapters.append((m[1], m[3]))
                lang_tags.append(m[2].strip())

    # Set default output format if not specified.
    if not args.format:
        args.format = 'pot' # Default to pot
        if args.clipboard:
            args.format = 'tab' # Default to "tab" if getting from clipboard for spreadsheet editing.
        if args.output: # Get output format from output filename, if specified.
            lower_ext = Path(args.output).suffix.lower()
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
        output_file = get_output_file(args)
        print(f'Write to file: {output_file}')
        if args.format == 'xml':
            temp_ogm_txt = ensure_nonexist('temp.ogm.txt')
            temp_mks = ensure_nonexist('temp.mks')
            temp_ogm_txt.write_text(output, encoding='utf-8') # use utf-8 for temp file
            cmd = ['mkvmerge', '-o', temp_mks]
            if args.lang:
                cmd += ['--chapter-language', args.lang]
            elif any(lang_tags):
                # assert there is only one language tag
                if not len(set(lang_tags)) == 1:
                    print('Warning: Multiple language tags detected! Will only use the first one.')
                # get first non-empty language tag
                lang_tag = [tag for tag in lang_tags if tag][0]
                print(f'Set language tag to {lang_tag} for XML chapter.')
                cmd += ['--chapter-language', lang_tag]
            cmd += ['--chapters', temp_ogm_txt]
            run(cmd)
            run(['mkvextract', temp_mks, 'chapters', output_file])
            temp_mks.unlink()
            temp_ogm_txt.unlink()
        else:
            with output_file.open('w', encoding=args.charset) as f:
                f.write(output)


if __name__ == '__main__':
    main()
