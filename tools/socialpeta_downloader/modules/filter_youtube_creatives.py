import os
import csv

def filter_youtube_rows():
    # Identify the current directory of the script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(current_dir, "scraped_creatives_1_to_10.csv")
    output_file = os.path.join(current_dir, "scraped_creatives_youtube_only.csv")
    
    if not os.path.exists(input_file):
        print(f"[-] Input file not found: {input_file}")
        return

    print(f"[*] Reading data from: {input_file}...")
    
    filtered_rows = []
    total_rows = 0
    
    # Read the original CSV file with UTF-8 encoding
    with open(input_file, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        for row in reader:
            total_rows += 1
            # Check if the youtube_url column has data
            if row.get('youtube_url') and row['youtube_url'].strip():
                filtered_rows.append(row)

    print(f"[*] Total rows scanned: {total_rows}")
    print(f"[*] Found {len(filtered_rows)} rows containing a YouTube link.")

    # Write to the new CSV file
    print(f"[*] Writing results to: {output_file}...")
    with open(output_file, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered_rows)
        
    print(f"[+] Done! Created file: {output_file}")

if __name__ == "__main__":
    filter_youtube_rows()
