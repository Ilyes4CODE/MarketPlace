import json

with open("MarketPlace/serviceAccountKey.json", "r") as f:
    data = json.load(f)

print(json.dumps(data))