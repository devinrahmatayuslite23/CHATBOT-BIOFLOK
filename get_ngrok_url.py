import requests
import time
import sys

print("Searching for Ngrok URL...")
for i in range(10):
    try:
        r = requests.get('http://127.0.0.1:4040/api/tunnels')
        data = r.json()
        if data['tunnels']:
            public_url = data['tunnels'][0]['public_url']
            print(f"URL_FOUND: {public_url}")
            sys.exit(0)
    except Exception as e:
        pass
    time.sleep(1)

print("Failed to find Ngrok URL")
