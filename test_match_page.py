import urllib.request
import re

url = "https://www.flashscorekz.com/match/IkY7Oqwp/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode("utf-8")
        print("HTML length:", len(html))
        
        # Search for participant IDs
        # Look for "id":"..." or participantEncodedIds = ['...', '...']
        ids = re.findall(r'"id":"(\w{8})"', html)
        print("Found IDs in HTML:", ids)
        
        # Look for country_id
        country_ids = re.findall(r'"countryId":(\d+)', html)
        print("Found country IDs:", country_ids)
        
        # Look for tournamentStageEncodedId
        stage_ids = re.findall(r'"tournamentStageId":"(\w{8})"', html)
        print("Found stage IDs:", stage_ids)
except Exception as e:
    print("Error:", e)
