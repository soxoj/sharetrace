from .router import detect_platform, get_parser

def parse_url(url):
    platform = detect_platform(url)
    if not platform:
        return {"error": "Unsupported platform or invalid URL"}
    
    parser = get_parser(platform)
    if not parser:
        return {"error": f"Parser module not found for {platform}"}
        
    return parser(url)