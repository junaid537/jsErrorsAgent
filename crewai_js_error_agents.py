import os
from dotenv import load_dotenv
load_dotenv()
import json
from typing import List, Dict, Any
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
import tiktoken
from langchain_openai import ChatOpenAI  # Updated import
import hashlib


class JavascriptErrorAgents:
    def __init__(self, openai_api_key: str):
        # Do not set the API key here; it is loaded from the environment via dotenv
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.5)
    def expert_Javascript_error_analyzer(self):
        return Agent(
        role="Expert JavaScript Error Analyzer",
        goal=(
            "Analyze a batch of independent JavaScript errors provided as a JSON object. "
            "Each key in the JSON represents a different error, containing an error snippet and surrounding code context. "
            "For every error, locate the snippet in the code context, identify the root cause of the bug, and suggest a fix."
        ),
        backstory=(
            "You are a highly experienced JavaScript debugging specialist. "
            "You've worked on large, complex frontend applications where logs contain many scattered errors. "
            "You're now given a JSON object with multiple errors, each with its relevant code snippet and surrounding code context. "
            "You must independently analyze each error, determine what caused it, and recommend a clean, production-ready fix."
        ),
        llm=self.llm,
        tools=[],
        verbose=True,
        memory=False,
        allow_delegation=False,
        max_iter=4
    )

    def expert_Javascript_fix_suggestor(self):
        return Agent(
        role="Expert JavaScript Fix Suggestor",
        goal=(
            "Receive code suggestions from the analyzer agent and return fixed JavaScript code "
            "for each error present in the original input JSON object. "
            "You must apply the suggestions to the respective `code_context` blocks to create clean, bug-free code."
        ),
        backstory=(
            "You are a senior frontend engineer who specializes in clean and accurate bug fixing. "
            "You are now given two inputs:\n"
            "1. A JSON object containing multiple JavaScript errors, with `error_snippet` and `code_context`.\n"
            "2. Suggestions from a JavaScript error analyzer agent.\n"
            "Your job is to apply each suggestion to the relevant code block and rewrite it so it no longer throws an error. "
            "Your fixes should be syntactically valid and production-ready."
        ),
        llm=self.llm,
        tools=[],  # optionally add a JS linter or formatter tool
        verbose=True,
        memory=False,
        allow_delegation=False,
        max_iter=4
    )

    def analyze_errors_task(self, input_json):
        return Task(
            description=(
                f"You are given this specific JavaScript error data:\n{json.dumps(input_json, indent=2)}\n\n"
                "Analyze the actual error provided above. For the error:\n"
                "1. Locate the error snippet in the code context.\n"
                "2. Explain the root cause of this specific error.\n"
                "3. Suggest a clean fix for this specific code.\n\n"
                "Return a list with one item:\n"
                "[\n"
                "  {\n"
                f"    'error': '{list(input_json.keys())[0]}',\n"
                "    'issue': '<specific root cause for this error>',\n"
                "    'suggestion': '<specific fix for this code>'\n"
                "  }\n"
                "]"
            ),
            agent=self.expert_Javascript_error_analyzer(),
            expected_output="List with one suggestion for the specific error",
            input=input_json
        )

    def fix_errors_task(self, original_errors_json, analyzer_output):
        return Task(
            description=(
                f"You are given:\n"
                f"1. This specific error data: {json.dumps(original_errors_json, indent=2)}\n"
                f"2. This analysis from the analyzer: {analyzer_output}\n\n"
                "Apply the specific suggestion to the specific code context provided above.\n"
                "Return the updated code block as bug-free JavaScript.\n\n"
                "Output format:\n"
                "[\n"
                "  {\n"
                f"    'error': '{list(original_errors_json.keys())[0]}',\n"
                "    'fixed_code': '<the corrected code for this specific error>'\n"
                "  }\n"
                "]"
            ),
            agent=self.expert_Javascript_fix_suggestor(),
            expected_output="Fixed JavaScript code for the specific error",
            input=original_errors_json,
            context=[analyzer_output]
        )

def batch_list(lst, batch_size):
    for i in range(0, len(lst), batch_size):
        yield lst[i:i + batch_size]

def hash_url(url):
    return hashlib.md5(url.encode('utf-8')).hexdigest()

if __name__ == "__main__":
    # Set your OpenAI API key here
    OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
    agents = JavascriptErrorAgents(OPENAI_API_KEY)

    # Load the RUM errors JSON
    with open("rum_errors_by_url_unique_description.json", "r", encoding="utf-8") as f:
        rum_errors_by_url = json.load(f)

    # Flatten all errors into a single list, each with its url and index
    all_errors = []
    for url, errors in rum_errors_by_url.items():
        for idx, error in enumerate(errors):
            all_errors.append({
                "url": url,
                "url_hash": hash_url(url),
                "idx": idx,
                "error": error
            })

    processed = 0
    total_errors = len(all_errors)
    for item in all_errors:
        error_input = {
            f"error_{item['url_hash']}_{item['idx']}": {
                "error_snippet": item["error"].get("error_part_in_code", ""),
                "code_context": item["error"].get("context_code", "")
            }
        }
        print(f"\n{'='*80}")
        print(f"PROCESSING ERROR {item['idx']} for {item['url']}")
        print(f"ERROR INPUT: {json.dumps(error_input, indent=2)}")
        print(f"{'='*80}")
        
        # Create tasks
        analyze_task = agents.analyze_errors_task(error_input)
        #fix_task = agents.fix_errors_task(error_input, analyzer_output="{analyzer_output}")
        fix_task = agents.fix_errors_task(error_input, analyzer_output=analyze_task)

        # Create and run the crew
        crew = Crew(
            agents=[agents.expert_Javascript_error_analyzer(), agents.expert_Javascript_fix_suggestor()],
            tasks=[analyze_task, fix_task],
            process=Process.sequential,
            verbose=True,
            memory=False
        )
        print(f"Processing error {item['idx']} for {item['url']} ...")
        result = crew.kickoff()
        # Save result to file
        out_filename = f"result_{item['url_hash']}_{item['idx']}.json"
        
        # Extract the important information from the result
        clean_result = {
            "url": item['url'],
            "error_index": item['idx'],
            "error_description": item["error"].get("error_description", ""),
            "error_snippet": item["error"].get("error_part_in_code", ""),
            "code_context": item["error"].get("context_code", ""),
            "line": item["error"].get("line", ""),
            "column": item["error"].get("column", ""),
            "analysis": {
                "issue": "",
                "suggestion": ""
            },
            "fixed_code": ""
        }
        
        # Try to extract analysis and fixed code from the result
        try:
            if hasattr(result, 'raw'):
                # Extract from raw output
                raw_output = result.raw
                if "tasks_output" in raw_output:
                    tasks_output = raw_output["tasks_output"]
                    if len(tasks_output) >= 2:
                        # Get analyzer output
                        analyzer_raw = tasks_output[0].get("raw", "")
                        if analyzer_raw:
                            # Try to parse the analyzer output
                            import re
                            issue_match = re.search(r"'issue':\s*'([^']*)'", analyzer_raw)
                            suggestion_match = re.search(r"'suggestion':\s*'([^']*)'", analyzer_raw)
                            
                            if issue_match:
                                clean_result["analysis"]["issue"] = issue_match.group(1)
                            if suggestion_match:
                                clean_result["analysis"]["suggestion"] = suggestion_match.group(1)
                        
                        # Get fixer output
                        fixer_raw = tasks_output[1].get("raw", "")
                        if fixer_raw:
                            # Extract the fixed code from the markdown code block
                            code_match = re.search(r'```javascript\n(.*?)\n```', fixer_raw, re.DOTALL)
                            if code_match:
                                clean_result["fixed_code"] = code_match.group(1)
        except Exception as e:
            print(f"Error extracting result data: {e}")
        
        # Save the clean result
        with open(out_filename, "w", encoding="utf-8") as outf:
            json.dump(clean_result, outf, indent=2)
        
        print(f"Saved result to {out_filename}")
        processed += 1
    print(f"\nDone! Processed {processed} errors (one by one) from the JSON file.")
