import json

def find_js_errors(rum_data):
    """
    Parses RUM data to find URLs with JavaScript errors.
    Returns a list of dicts with url, error_source, and user_agent.
    """
    errors_found = []
    # Support both direct list and 'rumBundles' key
    sessions = rum_data.get('rumBundles', rum_data) if isinstance(rum_data, dict) else rum_data

    for session in sessions:
        session_url = session.get("url")
        if not session_url:
            continue

        for event in session.get("events", []):
            if event.get("checkpoint") == "error":
                error_info = {
                    "url": session_url,
                    "error_source": event.get("source"),
                    "user_agent": session.get("userAgent")
                }
                errors_found.append(error_info)
    return errors_found

if __name__ == "__main__":
    # Example usage: load your RUM data from a file
    rum_json_file = 'rum_data.json'  # Change this to your actual file
    try:
        with open(rum_json_file, 'r') as f:
            data = json.load(f)
        detected_errors = find_js_errors(data)
        for error in detected_errors:
            print(f"Error detected on {error['url']} (User Agent: {error['user_agent']}): {error['error_source']}")
    except FileNotFoundError:
        print(f"File '{rum_json_file}' not found. Please provide your RUM data JSON file.") 