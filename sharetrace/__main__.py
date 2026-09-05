import argparse
import json
import sys
import traceback
from typing import Any, Dict, List

from .output import (
    Colors,
    print_banner,
    print_error,
    print_result,
    print_supported_platforms,
    write_output,
)
from .router import detect_platform, get_parser, get_supported_platforms, resolve_url


def _read_url_file(path: str) -> List[str]:
    urls: List[str] = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            urls.append(line)
    return urls


def _process_url(url: str, verbose: bool) -> Dict[str, Any]:
    record: Dict[str, Any] = {'url': url, 'platform': None}
    resolved = resolve_url(url)
    if resolved != url:
        record['resolved_url'] = resolved
    platform = detect_platform(resolved)
    if not platform:
        record['error'] = 'Unsupported platform or invalid URL'
        return record
    record['platform'] = platform

    parser_func = get_parser(platform)
    if not parser_func:
        record['error'] = f'Parser module not found for {platform}'
        return record

    try:
        result = parser_func(resolved)
    except Exception as e:
        if verbose:
            record['error'] = f'{type(e).__name__}: {e}'
            record['traceback'] = traceback.format_exc()
        else:
            record['error'] = 'Unable to extract information.'
        return record

    if 'error' in result:
        if verbose:
            record['error'] = result['error']
            details = {k: v for k, v in result.items() if k != 'error'}
            if details:
                record['error_details'] = details
        else:
            record['error'] = 'Unable to extract information.'
        return record

    record['data'] = result.get('data') or {}
    return record


def _print_record(record: Dict[str, Any], verbose: bool) -> None:
    if record.get('resolved_url'):
        print(f"{Colors.DIM}[→]{Colors.RESET} Resolved to "
              f"{Colors.CYAN}{record['resolved_url']}{Colors.RESET}\n")
    if 'error' in record:
        if verbose:
            details = record.get('error_details')
            print_error(record['error'], quiet=True, details=details)
            if 'traceback' in record:
                sys.stderr.write(record['traceback'])
        else:
            print_error(record['error'], quiet=True)
    else:
        print_result(record['platform'], {'data': record['data']}, quiet=True)


def _record_to_json(record: Dict[str, Any], verbose: bool, include_url: bool = False) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if include_url:
        out['url'] = record['url']
    if record.get('resolved_url'):
        out['resolved_url'] = record['resolved_url']
    if 'error' in record:
        if verbose:
            out['error'] = record['error']
            if 'error_details' in record:
                out.update(record['error_details'])
            if 'traceback' in record:
                out['traceback'] = record['traceback']
            if record.get('platform'):
                out['platform'] = record['platform']
            return out
        if include_url and record.get('platform'):
            out['platform'] = record['platform']
        out['error'] = 'Unable to extract information.'
        return out
    out['platform'] = record['platform']
    out['data'] = record['data']
    return out


def _print_progress(idx: int, total: int, record: Dict[str, Any]) -> None:
    platform = record.get('platform') or '-'
    if 'error' in record:
        tag = f"{Colors.RED}{Colors.BOLD}ERR  {Colors.RESET}"
        suffix = f"  {Colors.DIM}--{Colors.RESET} {record['error']}"
    else:
        tag = f"{Colors.GREEN}{Colors.BOLD}OK   {Colors.RESET}"
        suffix = ''
    if record.get('resolved_url'):
        suffix += f"  {Colors.DIM}→ {record['resolved_url']}{Colors.RESET}"
    print(f"[{idx}/{total}] {tag} {platform:<11} {record['url']}{suffix}")


def main():
    try:
        from colorama import init
        init()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(
        prog='sharetrace',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('url', nargs='?', help='The share link URL to analyze')
    parser.add_argument('-j', '--json', action='store_true', help='Output results as JSON')
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress banner and extra output')
    parser.add_argument('-l', '--list', action='store_true', help='List supported platforms')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Show detailed error info from the parser (raw message, status, traceback)')
    parser.add_argument('-i', '--input', metavar='FILE',
                        help='Read URLs to analyze from FILE (one per line; blanks and #comments ignored)')
    parser.add_argument('-o', '--output', metavar='FILE',
                        help='Write results to FILE; format inferred from extension (.csv or .json)')

    if ('-h' in sys.argv or '--help' in sys.argv) and ('-q' not in sys.argv and '--quiet' not in sys.argv):
        print_banner()

    args = parser.parse_args()

    if args.list:
        if args.json:
            print(json.dumps({'platforms': get_supported_platforms()}, indent=2))
        else:
            if not args.quiet:
                print_banner()
            print_supported_platforms()
        sys.exit(0)

    if args.input and args.url:
        print_error('Use either a positional URL or --input FILE, not both.', quiet=args.quiet)
        sys.exit(2)

    if not args.input and not args.url:
        if not args.quiet:
            print_banner()
        parser.print_help()
        sys.exit(1)

    if args.output:
        lower = args.output.lower()
        if not (lower.endswith('.csv') or lower.endswith('.json')):
            print_error(f"--output: unsupported extension for {args.output!r}; use .csv or .json",
                        quiet=args.quiet)
            sys.exit(2)

    if args.input:
        try:
            urls = _read_url_file(args.input)
        except OSError as e:
            print_error(f'Could not read --input file: {e}', quiet=args.quiet)
            sys.exit(2)
        if not urls:
            print_error(f'No URLs found in {args.input}', quiet=args.quiet)
            sys.exit(1)
    else:
        urls = [args.url]

    batch = args.input is not None
    show_banner = not args.quiet and not args.json

    if show_banner:
        print_banner()
        if batch:
            print(f"[🔍] Analyzing {len(urls)} link(s)...\n")
        else:
            platform_guess = detect_platform(urls[0])
            label = platform_guess.capitalize() if platform_guess else 'share'
            print(f"[🔍] Analyzing {label} link...\n")

    records: List[Dict[str, Any]] = []
    any_error = False
    for idx, url in enumerate(urls, 1):
        record = _process_url(url, args.verbose)
        records.append(record)
        if 'error' in record:
            any_error = True

        if args.json:
            continue
        if batch:
            if not args.quiet:
                _print_progress(idx, len(urls), record)
        else:
            _print_record(record, args.verbose)

    if args.json and not args.output:
        if batch:
            payload = [_record_to_json(r, args.verbose, include_url=True) for r in records]
        else:
            payload = _record_to_json(records[0], args.verbose)
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    if args.output:
        # Build records appropriate for the requested file format.
        if args.output.lower().endswith('.json'):
            file_records = [
                _record_to_json(r, args.verbose, include_url=batch) for r in records
            ]
        else:
            file_records = records
        try:
            write_output(file_records, args.output)
        except (OSError, ValueError) as e:
            print_error(f'Could not write --output file: {e}', quiet=True)
            sys.exit(2)
        if not args.quiet:
            ok = sum(1 for r in records if 'error' not in r)
            print(f"\n{Colors.GREEN}[✓]{Colors.RESET} Wrote {ok}/{len(records)} result(s) to {args.output}")

    sys.exit(1 if any_error and not batch else 0)


if __name__ == '__main__':
    main()
