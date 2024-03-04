# AI command suggestions anywhere with Python

![Example usage](.github/example.png)

Using OpenAI GPT-3 (or GPT-4), get powerful AI command suggestions anywhere with Python. Uses GPT-4 as fallback when command fails or user wants to improve the current command.

User's system is given as context, or if the command fails to execute it is given as context to the AI.

## Installation

  ```bash
  pip install -r requirements.txt
  ```

I also recommend to setup a `alias` to run the script from anywhere in the terminal.

## Usage

  ```bash
  $ askg list all my files alphabetically
Thinking...
Suggestions
1. ls -l
The 'ls' command is used to list files and directories. The '-l' flag is used to display the results in a long listing format, which includes additional information such as file permissions, owner, group, size, and last modified date. By default, the 'ls' command lists files alphabetically.
  ```