# Elgato Prompter Text

A tiny cross-platform CLI to manage Elgato Prompter script JSON files.
It can add, delete, and list prompts in your Texts folder and keeps AppSettings.json in sync (one directory up from Texts).


**EXPERIMENTAL**
**NOTE**: Elgato Camera Hub app should be QUIT / CLOSED / NOT RUNNING when using CLI. 

### JSON Structure

The JSON shape the tool writes/reads:

\`\`\`json
{
  "GUID": "494D4229-59C8-448C-8E32-B93ED48505A2",
  "chapters": ["..."],
  "friendlyName": "Makepath Introduction",
  "index": 1
}
\`\`\`

## Features

- **add** – create a new JSON prompt file (auto GUID, auto index unless you supply one)
- **del** – delete prompt file(s) by GUID, friendly name, or filename
- **ls** – list prompts as a clean table (uses pandas if installed)
- **AppSettings sync** – automatically adds/removes the prompt’s GUID in
../AppSettings.json under the key applogic.prompter.libraryList

#### Installation
Requirements

Python 3.9+

(Optional) pandas (used by ls for pretty tables)

Install with pipx (recommended)

##### Get the code
```bash
git clone https://github.com/brendancol/elgato_prompter_text_cli.git
cd elgato_prompter_text_cli
```

##### From the project directory (where pyproject.toml lives)
```bash
pip install .            # minimal install
```

##### …or include optional table deps:
```bash
pip install .[table]     # installs pandas for nicer tables
```

This exposes the console script:

```bash
elgato-prompter-text --help
```

##### Configure the scripts directory

The tool needs to know where your Texts directory is.

You can provide it in two ways:

Environment variable: ELGATO_PROMPTER_DIR

CLI flag on each command: --dir /path/to/Texts

The tool assumes AppSettings.json is **exactly one** directory up from Texts.

Directory layout:

```bash
<parent>/
  AppSettings.json
  Texts/
    *.json  <-- your prompt files
```

Common paths & examples

###### macOS (OS X) – typical location:

```bash
export ELGATO_PROMPTER_DIR=~/Library/Application\ Support/Elgato/Camera\ Hub/Texts
```


(Note the backslashes for spaces.)

###### Windows (PowerShell):

```bash
$env:ELGATO_PROMPTER_DIR="$env:APPDATA\Elgato\CameraHub\Texts"
```
