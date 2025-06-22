#Purpose: Tests the CrewAI system with just ONE error to verify it works
'''
import os
from dotenv import load_dotenv
load_dotenv()
import json
from typing import List, Dict, Any
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
import tiktoken
from langchain_openai import ChatOpenAI
import hashlib

class JavascriptErrorAgents:
    def __init__(self, openai_api_key: str):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.5)
        
    def expert_Javascript_error_analyzer(self):
        return Agent(
            role="Expert JavaScript Error Analyzer and Senior Software Development Engineer",
            goal="Given the error message and the relevant code context/ code snippet, provide detailed root cause analysis on the error and steps to fix it!!",
            backstory="You are a highly experienced JavaScript debugging specialist who analyzes real code errors.",
            llm=self.llm,
            tools=[],
            verbose=True,
            memory=False,
            allow_delegation=False,
            max_iter=4
        )

    def expert_Javascript_fix_suggestor(self):
        return Agent(
            role="Expert JavaScript Debugger and Senior Javascript Developer",
            goal="Apply specific fixes to JavaScript code based on error analysis given by expert_Javascript_error_analyzer and return the new fixed code",
            backstory="You are a senior Javascript Frontend Engineer who fixes real JavaScript bugs.",
            llm=self.llm,
            tools=[],
            verbose=True,
            memory=False,
            allow_delegation=False,
            max_iter=4
        )

    def analyze_errors_task(self, input_json):
        return Task(
            description=(
                f"You are given this specific JavaScript error message: {input_json[list(input_json.keys())[0]]['error_description']} and specific error line from the code:\n{input_json[list(input_json.keys())[0]]['error_snippet']}\n\n"
                f"The relevant code context holding that error is:\n{input_json[list(input_json.keys())[0]]['code_context']}\n\n"
                "You are also given code_context around the error_snippet! The entire code context might not be syntactically absolutely right or complete, as few lines are fetched around the error snippet so as not to breach input token limit of LLM! "
                "First locate the error line inside the context code provided to you then match the actual error description provided above. For the error:\n"
                "1. Locate the error snippet in the code context.\n"
                "2. Explain the root cause of this specific error.\n"
                "3. Suggest steps to fix the error in the code!!!!!\n\n"
                
                "Return the suggestion:\n"
                "[\n"
                "  {\n"
                f"   'error': '{list(input_json.keys())[0]}',\n"
                "    'issue': '<specific root cause for this error>',\n"
                "    'suggestion': '<specific fix for this code>'\n"
                "    'Steps to fix the code': '<Bullet points to fix the error>'\n"
                "  }\n"
                "]"
            ),
            agent=self.expert_Javascript_error_analyzer(),
            expected_output="List with one best suggestion for the specific error",
            input=input_json
        )

    def fix_errors_task(self, original_errors_json, analyzer_output):
        return Task(
            description=(
                f"You are given this specific JavaScript error message: {original_errors_json[list(original_errors_json.keys())[0]]['error_description']} and specific error line from the code:\n{original_errors_json[list(original_errors_json.keys())[0]]['error_snippet']}\n\n"
                f"IMPORTANT: You will receive the analysis from the Expert JavaScript Error Analyzer in the context from the previous task. Use his suggestions to fix that specific error in the code context and return bug free code context.\n\n"
                f"The relevant code context holding that error is:\n{original_errors_json[list(original_errors_json.keys())[0]]['code_context']}\n\n"
                "Just Return the updated code block after applying the fixes suggested by the Expert JavaScript Error Analyzer.\n\n"
                "Output format:\n"
                "[\n"
                "  {\n"
                #f"    'error': '{list(original_errors_json.keys())[0]}',\n"
                "    'fixed_code': '<the corrected code for this specific error>'\n"
                "  }\n"
                "]"
            ),
            agent=self.expert_Javascript_fix_suggestor(),
            expected_output="Fixed JavaScript code for the specific error using the suggestion from Expert JavaScript Debugger and Senior Javascript Developer",
            input=original_errors_json,
            context=[analyzer_output]
        )

def hash_url(url):
    return hashlib.md5(url.encode('utf-8')).hexdigest()

if __name__ == "__main__":
    OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
    agents = JavascriptErrorAgents(OPENAI_API_KEY)

    # Load the RUM errors JSON
    with open("rum_errors_by_url_unique_description.json", "r", encoding="utf-8") as f:
        rum_errors_by_url = json.load(f)

    # Get just the first error for testing
    first_url = list(rum_errors_by_url.keys())[0]
    first_error = rum_errors_by_url[first_url][0]
    
    error_input = {
        f"error_{hash_url(first_url)}_0": {
            "error_description": first_error.get("error_description", ""),
            "error_snippet": first_error.get("error_part_in_code", ""),
            "code_context": first_error.get("context_code", "")
        }
    }
    
    print(f"TESTING WITH REAL ERROR DATA:")
    print(f"URL: {first_url}")
    print(f"Error: {first_error.get('error_description', 'N/A')}")
    print(f"Input: {json.dumps(error_input, indent=2)}")
    print("="*80)
    
    # Create tasks
    analyze_task = agents.analyze_errors_task(error_input)
    fix_task = agents.fix_errors_task(error_input, analyzer_output=analyze_task)
    fix_task.context = [analyze_task]

    # Create and run the crew
    crew = Crew(
        agents=[agents.expert_Javascript_error_analyzer(), agents.expert_Javascript_fix_suggestor()],
        tasks=[analyze_task, fix_task],
        process=Process.sequential,
        verbose=True,
        memory=False
    )
    
    print("Running CrewAI...")
    result = crew.kickoff()
    
    # Extract suggestion and fixed code from crew result
    if hasattr(result, 'raw'):
        result_data = result.raw
    elif hasattr(result, 'dict'):
        result_data = result.dict()
    elif hasattr(result, 'to_dict'):
        result_data = result.to_dict()
    else:
        result_data = str(result)
    
    # Parse the result to extract suggestion and fixed code
    if isinstance(result_data, str):
        # Try to extract JSON from string if it's wrapped
        import re
        json_match = re.search(r'\[.*\]', result_data, re.DOTALL)
        if json_match:
            try:
                result_data = json.loads(json_match.group())
            except:
                pass
    
    # Save the full result
    # Safely extract raw data from each task output
    suggestion_output = analyze_task.output.raw if hasattr(analyze_task.output, 'raw') else str(analyze_task.output)
    fixed_code_output = fix_task.output.raw if hasattr(fix_task.output, 'raw') else str(fix_task.output)

    # Save the result
    out_filename = f"test_result_{hash_url(first_url)}_0.json"
    with open(out_filename, "w", encoding="utf-8") as outf:
        json.dump({
            "crew_output": result_data,
            "suggestion": suggestion_output,
            "fixed_code": fixed_code_output
        }, outf, indent=2)

    print(f"Saved test result to {out_filename}")'''