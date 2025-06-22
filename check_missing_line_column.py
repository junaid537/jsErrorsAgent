import json

# Load the RUM errors JSON
with open("rum_errors_by_url_unique_description.json", "r", encoding="utf-8") as f:
    rum_errors_by_url = json.load(f)

# Check for errors missing line and column numbers
errors_without_line_column = []
total_errors = 0

print("=" * 80)
print("CHECKING FOR ERRORS WITHOUT LINE AND COLUMN NUMBERS")
print("=" * 80)

for url, errors in rum_errors_by_url.items():
    for idx, error in enumerate(errors):
        total_errors += 1
        
        # Check if line or column is missing
        line = error.get("line")
        column = error.get("column")
        
        if line is None or column is None:
            errors_without_line_column.append({
                "url": url,
                "error_index": idx,
                "line": line,
                "column": column,
                "error_description": error.get("error_description", "N/A"),
                "error_source": error.get("error_source", "N/A")
            })

print(f"Total errors checked: {total_errors}")
print(f"Errors without line/column: {len(errors_without_line_column)}")
print("=" * 80)

if errors_without_line_column:
    print("\n❌ ERRORS FOUND WITHOUT LINE/COLUMN NUMBERS:")
    print("-" * 80)
    for error in errors_without_line_column:
        print(f"URL: {error['url']}")
        print(f"Error Index: {error['error_index']}")
        print(f"Line: {error['line']}")
        print(f"Column: {error['column']}")
        print(f"Description: {error['error_description']}")
        print(f"Source: {error['error_source']}")
        print("-" * 40)
else:
    print("\n✅ ALL ERRORS HAVE LINE AND COLUMN NUMBERS!")
    print("=" * 80)

# Also check for other important fields
print("\n" + "=" * 80)
print("CHECKING FOR OTHER MISSING IMPORTANT FIELDS")
print("=" * 80)

missing_error_snippet = []
missing_context_code = []

for url, errors in rum_errors_by_url.items():
    for idx, error in enumerate(errors):
        if not error.get("error_part_in_code"):
            missing_error_snippet.append(f"{url} - Error {idx}")
        
        if not error.get("context_code"):
            missing_context_code.append(f"{url} - Error {idx}")

print(f"Errors missing 'error_part_in_code': {len(missing_error_snippet)}")
print(f"Errors missing 'context_code': {len(missing_context_code)}")

if missing_error_snippet:
    print("\n❌ ERRORS MISSING 'error_part_in_code':")
    for item in missing_error_snippet[:5]:  # Show first 5
        print(f"  - {item}")
    if len(missing_error_snippet) > 5:
        print(f"  ... and {len(missing_error_snippet) - 5} more")

if missing_context_code:
    print("\n❌ ERRORS MISSING 'context_code':")
    for item in missing_context_code[:5]:  # Show first 5
        print(f"  - {item}")
    if len(missing_context_code) > 5:
        print(f"  ... and {len(missing_context_code) - 5} more")

if not missing_error_snippet and not missing_context_code:
    print("\n✅ ALL ERRORS HAVE REQUIRED CODE FIELDS!")

print("=" * 80) 