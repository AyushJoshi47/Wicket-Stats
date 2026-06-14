import json

with open("new_mapped.json") as f:
    data = json.load(f)

full_names = sorted(set(data.values()))

with open("full_names.json", "w") as f:
    json.dump(full_names, f, indent=4)

print(f"Done. {len(full_names)} unique names saved to full_names.json")