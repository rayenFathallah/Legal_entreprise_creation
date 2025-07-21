import json
import pandas as pd

# 1) Load the JSON data from ./scraped_data.json
with open("scraped_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# 2) If "pdf_local_paths" is a list, convert it into a semicolon-separated string
for entry in data:
    if isinstance(entry.get("pdf_local_paths"), list):
        entry["pdf_local_paths"] = ";".join(entry["pdf_local_paths"])

# 3) Create a DataFrame from the list of dicts
df = pd.DataFrame(data)

# 4) Write to Excel
#    You can install openpyxl (or xlsxwriter) if it isn’t already: pip install openpyxl
df.to_excel("scraped_data.xlsx", index=False, engine="openpyxl")

print("Converted scraped_data.json → scraped_data.xlsx")
