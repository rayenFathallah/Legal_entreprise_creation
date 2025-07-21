import json
import os

# Read the scraped data
with open('scraped_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Process each entry
for entry in data:
    pdf_paths = entry['pdf_local_paths']
    json_contents = []
    
    for pdf_path in pdf_paths:
        # Convert PDF path to JSON path
        json_path = pdf_path.replace('.pdf', '.json')
        
        try:
            # Read the JSON file
            with open(json_path, 'r', encoding='utf-8') as f:
                json_content = json.load(f)
                json_contents.append(json_content)
        except Exception as e:
            print(f"Error reading {json_path}: {e}")
            json_contents.append(None)
    
    # Replace pdf_local_paths with json_contents
    entry['json_contents'] = json_contents
    del entry['pdf_local_paths']

# Write the updated data back to file
with open('scraped_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print("✅ Successfully updated scraped_data.json with JSON contents")