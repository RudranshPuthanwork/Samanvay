import urllib.request
import re

req = urllib.request.Request("https://maps.protomaps.com/assets/builds-Cdq4B9B1.js", headers={"User-Agent": "Mozilla/5.0"})
try:
    content = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
    urls = re.findall(r"https?://[^\s\"\'\<\>]+", content)
    print("Found urls:", urls)
    keys = re.findall(r"build\.protomaps\.com/[^\s\"\'\<\>]+", content)
    print("Found keys:", keys)
    # Also search for api or json
    apis = re.findall(r"/[a-zA-Z0-9_\-\./]+\.json", content)
    print("Found json endpoints:", apis)
except Exception as e:
    print("Error:", e)

