import json

# Load the RUM errors JSON
with open("rum_errors_by_url_unique_description.json", "r", encoding="utf-8") as f:
    rum_errors_by_url = json.load(f)

# Calculate statistics
total_urls = len(rum_errors_by_url)
total_errors = sum(len(errors) for errors in rum_errors_by_url.values())

print("=" * 60)
print("RUM ERRORS STATISTICS")
print("=" * 60)
print(f"Total URLs: {total_urls}")
print(f"Total Errors: {total_errors}")
print("=" * 60)

# Print details for each URL
print("\nDETAILED BREAKDOWN:")
print("-" * 60)
for url, errors in rum_errors_by_url.items():
    print(f"URL: {url}")
    print(f"  Errors: {len(errors)}")
    print()

print("=" * 60)
print("SUMMARY:")
print(f"Average errors per URL: {total_errors / total_urls:.2f}")
print("=" * 60) 