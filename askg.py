from typing import List
import openai
from openai.types.chat.chat_completion import ChatCompletion
import sys
import json
import subprocess
from colorama import Fore, Style
from dataclasses import dataclass
import platform

import environ
envf = environ.Env()
envf.read_env()
API_KEY = envf.get_value('OPENAI_API_KEY')
if len(API_KEY) < 8:
    print(Fore.RED + "Error: OPENAI_API_KEY seems invalid" + Style.RESET_ALL)
    sys.exit(1)

openai.api_key = API_KEY

BASE_MODEL_NAME = "gpt-4o-mini"
IMPROVED_MODEL_NAME = "gpt-4o"

@dataclass
class Suggestion:
    command: str
    explanation: str
    
    def __str__(self) -> str:
        return json.dumps({'command': self.command, 'explanation': self.explanation})
    
    @staticmethod
    def from_json(json_string: str) -> 'Suggestion':
        json_dict = json.loads(json_string)
        return Suggestion(json_dict['command'], json_dict['explanation'])

def do_openai_call(model, messages, n=2):
    return openai.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=256,
        n=n,
        response_format={"type": "json_object"},
        temperature=0.5,
    )

def parse_response_to_suggestions(response: ChatCompletion):
    try:
        return [Suggestion.from_json(suggestion.message.content or '') for suggestion in response.choices]
    except KeyError:
        print(Fore.RED + "Error: Invalid response from OpenAI API" + Style.RESET_ALL)
        print(Style.DIM + str(response) + Style.RESET_ALL)
        sys.exit(1)

def get_system_info():
    system = platform.system()
    if system == 'posix':
        return subprocess.run(['uname', '-a'], stdout=subprocess.PIPE, text=True).stdout.strip()
    return system

def generate_suggestions(query: str) -> List[Suggestion]:
    system_info = get_system_info()
    messages = [
        {
            'role': 'system',
            'content': f"Generate a executable bash suggestion for the users query, for system: '{system_info}'. Give the command and also a technical explanation of what the command does and it constructed. Present in JSON format with keys 'command' and 'explanation'"
        },
        {
            'role': 'user',
            'content': f'QUERY: {query}'
        }
    ]
    
    response = do_openai_call(BASE_MODEL_NAME, messages)
    suggestions =  parse_response_to_suggestions(response)
    return suggestions

def improve_suggestions(query: str, old_suggestions: List[Suggestion]) -> List[Suggestion]:
    old_suggestions_text = '\n'.join([str(suggestion) for suggestion in old_suggestions])
    system_info = get_system_info()
    messages = [
        {
            'role': 'system',
            'content': f"Improve the bash command suggestions given by a another AI. Meaning the user didn't like the another suggestions and want a new command, give a improved suggestion based on user query and the discareded suggestions, for system: '{system_info}'. Give the command and also a technical explanation of what the command does and it constructed, also how it is better/different from the others. Present in JSON format with keys 'command' and 'explanation'"
        },
        {
            'role': 'user',
            'content': f'USER QUERY: {query}\nDISCARDED SUGGESTIONS: {old_suggestions_text}'
        }
    ]
    response = do_openai_call(IMPROVED_MODEL_NAME, messages)
    suggestions =  parse_response_to_suggestions(response)
    return suggestions

def fix_suggestion(query, used_suggestion, error_code, error_output):
    system_info = get_system_info()
    messages = [
        {
            'role': 'system',
            'content': f"Fix the bash command suggestion given by a another AI. The command should directly answer the users query, but fixed to work on the users system: {system_info}. Give the command and also a technical explanation of what the command does and it constructed, but most importantly: what the issue was and how it was fixed. Present in JSON format with keys 'command' and 'explanation'. Start by writing the 'explanation' first."
        },
        {
            'role': 'user',
            'content': f'USER QUERY: {query}\nUSED SUGGESTION: {used_suggestion}\nERROR CODE: {error_code}\nSTDERR: {error_output}'
        }
    ]
    response = do_openai_call(IMPROVED_MODEL_NAME, messages, n=1)
    suggestions =  parse_response_to_suggestions(response)
    return suggestions

def remove_duplicates(suggestions: List[Suggestion]) -> List[Suggestion]:
    seen = set()
    new_suggestions = []
    for suggestion in suggestions:
        if suggestion.command not in seen:
            seen.add(suggestion.command)
            new_suggestions.append(suggestion)
    return new_suggestions

def print_suggestions(suggestions: List[Suggestion], title="Suggestions"):
    print(Style.BRIGHT + Fore.YELLOW + title + Style.RESET_ALL)
    for i, suggestion in enumerate(suggestions, start=1):
        print(Fore.CYAN + f"{i}. {suggestion.command}")
        print(Style.DIM + suggestion.explanation + Style.RESET_ALL)
        print()

def get_choice(suggestions: List[Suggestion], can_improve=True):
    choices_numbers = ', '.join([str(i) for i in range(1, len(suggestions) + 1)])
    # replace last , with 'or'
    choices_numbers = choices_numbers[::-1].replace(',', 'ro ', 1)[::-1]
    improvement_str =", discard and improve with 'i'" if can_improve else ""
    if len(suggestions) > 1:
        choice = input(Fore.GREEN + f"Choose an option ({choices_numbers}){improvement_str} or press any other key to exit: "+ Style.RESET_ALL)
    else:
        choice = input(Fore.GREEN + f"Type 'y' to execute the following command{improvement_str} or press any other key to exit: "+ Style.RESET_ALL)
    
    # Reset all colorama styles
    print(Style.RESET_ALL, Fore.RESET, end='')
    return choice

def do_command(query: str, suggestion: Suggestion):
    print()
    try:
        subprocess.run(
            suggestion.command, 
            shell=True, 
            check=True, 
            stderr=subprocess.PIPE, 
            text=True
        )
    except subprocess.CalledProcessError as e:
        print(Fore.RED + "Error: Command failed" + Style.RESET_ALL)
        error_code = e.returncode
        error_output = e.stderr
        print("Error output:" + Style.DIM, error_output, Style.RESET_ALL)
        
        choice = input(Fore.GREEN + f"Type 'y' to fix the command or press any other key to exit: ")
        if choice == 'y':
            print(Fore.YELLOW + Style.DIM + "\nFixing suggestion..." + Style.RESET_ALL)
            suggestions = fix_suggestion(query, suggestion, error_code, error_output)
            # Remove duplicate suggestion by comparing the command
            suggestions = remove_duplicates(suggestions)
            
            # Print suggestions
            print_suggestions(suggestions, title="Fixed suggestions")
            
            # Get choice
            choice = get_choice(suggestions, can_improve=False)
            
            # Execute choice
            for n in range(1, len(suggestions) + 1):
                if choice == str(n) or (choice == 'y' and n == 1):
                    do_command(query, suggestions[n - 1])
                    break
            else:
                print(Fore.RED + "\n[*] Exiting...")
                sys.exit()
        else:
            print(Fore.RED + "\n[*] Exiting...")
            sys.exit()

def main():
    if len(sys.argv) < 2:
        print(Fore.RED + "Usage: askg.py <query>")
        sys.exit(1)
    # Parse args to query
    query = " ".join(sys.argv[1:])
    
    # Generate suggestions
    print(Fore.YELLOW + Style.DIM + "Thinking..." + Style.RESET_ALL, end='\r')
    suggestions = generate_suggestions(query)
    
    # Remove duplicate suggestion by comparing the command
    suggestions = remove_duplicates(suggestions)
    
    # Remove 'Thinking...' from the output
    print("\r", end='')

    # Print suggestions
    print_suggestions(suggestions)
    
    # Get choice
    choice = get_choice(suggestions)
    
    if choice == 'i': # Improve suggestions
        print(Fore.YELLOW + Style.DIM + "\nThinking harder..." + Style.RESET_ALL)
        suggestions = improve_suggestions(query, suggestions)
        # Remove duplicate suggestion by comparing the command
        suggestions = remove_duplicates(suggestions)
        
        # Print suggestions
        print_suggestions(suggestions, title="Improved suggestions")
        
        # Get choice
        choice = get_choice(suggestions, can_improve=False)
    
    # Execute choice    
    for n in range(1, len(suggestions) + 1):
        if choice == str(n) or (choice == 'y' and n == 1):
            do_command(query, suggestions[n - 1])
            break
    else:
        print(Fore.RED + "\n[*] Exiting...")
        sys.exit()

if __name__ == "__main__":
    main()
