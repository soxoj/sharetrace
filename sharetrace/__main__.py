import argparse
import sys
import json
from .output import print_result, print_error, print_supported_platforms, print_banner
from .router import detect_platform, get_parser, get_supported_platforms

def main():
    try:
        from colorama import init
        init()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(
        prog='sharetrace',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('url', nargs='?', help='The share link URL to analyze')
    parser.add_argument('-j', '--json', action='store_true', help='Output results as JSON')
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress banner and extra output')
    parser.add_argument('-l', '--list', action='store_true', help='List supported platforms')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Show detailed error info from the parser (raw message, status, traceback)')
    
    if ('-h' in sys.argv or '--help' in sys.argv) and ('-q' not in sys.argv and '--quiet' not in sys.argv):
        print_banner()

    args = parser.parse_args()
    
    if args.list:
        if args.json:
            print(json.dumps({"platforms": get_supported_platforms()}, indent=2))
        else:
            if not args.quiet:
                print_banner()
            print_supported_platforms()
        sys.exit(0)
        
    if not args.url and not args.list:
        if not args.quiet:
            print_banner()
        parser.print_help()
        sys.exit(1)
        
    url = args.url
    platform = detect_platform(url)
    
    if not platform:
        if args.json:
            print(json.dumps({"error": "Unsupported platform or invalid URL"}, indent=2))
        else:
            print_error("Unsupported platform or invalid URL", quiet=args.quiet)
            print("Tip: Use --list to see supported platforms.")
        sys.exit(1)
        
    parser_func = get_parser(platform)
    
    if not parser_func:
        if args.json:
            print(json.dumps({"error": f"Parser module not found for {platform}"}, indent=2))
        else:
            print_error(f"Parser module not found for {platform}", quiet=args.quiet)
        sys.exit(1)
        
    if not args.quiet and not args.json:
        print_banner() 
        print(f"[🔍] Analyzing {platform.capitalize()} link...\n")
    try:
        result = parser_func(url)

        if args.json:
            if 'data' in result:
                result['platform'] = platform
            if 'error' in result and not args.verbose:
                # In non-verbose mode, mask raw parser error and strip debug fields
                result = {"error": "Unable to extract information."}
            print(json.dumps(result, indent=2))
        else:
            if 'error' in result:
                if args.verbose:
                    details = {k: v for k, v in result.items() if k != 'error'}
                    print_error(result['error'], quiet=True, details=details or None)
                else:
                    print_error("Unable to extract information.", quiet=True)
            else:
                print_result(platform, result, quiet=True)

    except Exception as e:
        if args.verbose:
            import traceback
            if args.json:
                print(json.dumps({
                    "error": str(e),
                    "exception_type": type(e).__name__,
                    "traceback": traceback.format_exc(),
                }, indent=2))
            else:
                print_error(f"{type(e).__name__}: {e}", quiet=args.quiet)
                traceback.print_exc()
        else:
            if args.json:
                print(json.dumps({"error": "Unable to extract information."}, indent=2))
            else:
                print_error("Unable to extract information.", quiet=args.quiet)
        sys.exit(1)

if __name__ == "__main__":
    main()