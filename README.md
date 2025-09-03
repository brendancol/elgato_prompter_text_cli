#### elgato-prompter-text

A tiny cross-platform CLI to manage Elgato Prompter script JSON files.
It can add, delete, and list prompts in your Texts folder and keeps AppSettings.json in sync (one directory up from Texts).

JSON shape the tool writes/reads:

```json
{
  "GUID": "494D4229-59C8-448C-8E32-B93ED48505A2",
  "chapters": ["..."],
  "friendlyName": "Makepath Introduction",
  "index": 1
}
```

#### Features

add – create a new JSON prompt file (auto GUID, auto index unless you supply one)

del – delete prompt file(s) by GUID, friendly name, or filename

ls – list prompts as a clean table (uses pandas if installed)

AppSettings sync – automatically adds/removes the prompt’s GUID in
../AppSettings.json under the key applogic.prompter.libraryList

#### Installation
Requirements

Python 3.9+

(Optional) pandas (used by ls for pretty tables)

Install with pipx (recommended)
# From the project directory (where pyproject.toml lives)
pipx install .            # minimal install
# …or include optional table deps:
pipx install .[table]     # installs pandas for nicer tables

Install with pip
pip install .             # minimal install
# or with pandas
pip install ".[table]"


This exposes the console script:

elgato-prompter-text

Configure the scripts directory

The tool needs to know where your Texts directory is. You can provide it in two ways:

Environment variable: ELGATO_PROMPTER_DIR

CLI flag on each command: --dir /path/to/Texts

The tool assumes AppSettings.json is exactly one directory up from Texts.
Directory layout:

<parent>/
  AppSettings.json
  Texts/
    *.json  <-- your prompt files

Common paths & examples

macOS (OS X) – typical location:

export ELGATO_PROMPTER_DIR=~/Library/Application\ Support/Elgato/Camera\ Hub/Texts


(Note the backslashes for spaces.)

Windows (PowerShell):

$env:ELGATO_PROMPTER_DIR="$env:APPDATA\Elgato\CameraHub\Texts"


Example resolved path: C:\Users\<you>\AppData\Roaming\Elgato\CameraHub\Texts

Linux (example/custom):

export ELGATO_PROMPTER_DIR=~/Elgato/CameraHub/Texts


Prefer not to set an env var? Pass --dir whenever you run the command:

elgato-prompter-text --dir "/full/path/to/Texts" ls

#### Quick start
# 1) Point the CLI at your Texts directory (choose one)
export ELGATO_PROMPTER_DIR=~/Library/Application\ Support/Elgato/Camera\ Hub/Texts
# or pass --dir on each command

# 2) Create a new prompt
```bash
elgato-prompter-text add \
  --name "Makepath Introduction" \
  --chapter "Here is the script we are going to have on the screen" \
  --chapter "Some additional Text Here" \
  --chapter "Hi, My name is Brendan and I lead the product innovation team at Makepath." \
  --chapter "Thanks so much for joining us today" \
  --chapter "What can i do to make things easier for you"
```

# 3) List prompts (auto-uses pandas if installed)
```bash
elgato-prompter-text ls
```

# 4) Delete by GUID
```bash
elgato-prompter-text del --guid 494D4229-59C8-448C-8E32-B93ED48505A2
```


What happens:

Add writes NNN_slug_GUID.json into Texts/ and appends the GUID to ../AppSettings.json under applogic.prompter.libraryList (no duplicates).

Del removes the matching JSON file(s) and removes their GUID(s) from ../AppSettings.json.

Commands & options
add

Create a new prompt JSON file and update AppSettings.json.

elgato-prompter-text add \
  --name "Friendly Name" \
  [--chapter "Line 1"] [--chapter "Line 2"] ... \
  [--chapters-file ./chapters.txt] \
  [--from-stdin] \
  [--index 7] \
  [--guid 12345678-ABCD-... ] \
  [--dir /path/to/Texts]


--name (required): becomes friendlyName

--chapter (repeatable): each adds a chapter line

--chapters-file: read one chapter per line from a file

--from-stdin: read chapters from stdin (one per line)

--index: integer; default = max existing index + 1

--guid: supply your own; default is auto-generated (uppercase)

--dir: override ELGATO_PROMPTER_DIR

Dry run (see JSON without writing a file):

elgato-prompter-text add --name "Test" --chapter "Line" --dry-run

del

Delete prompt JSON and remove GUID(s) from AppSettings.json.

elgato-prompter-text del \
  [--guid GUID] \
  [--name "Friendly Name"] \
  [--file filename.json] \
  [-y] \
  [--dir /path/to/Texts]


Provide one of: --guid, --name, or --file

-y/--yes confirms deletion when multiple files match a name

ls

Show a table of current prompts in Texts/.

elgato-prompter-text ls \
  [--columns index friendlyName GUID chaptersCount file] \
  [--sort index] [--reverse] \
  [--limit 20] \
  [--pandas] \
  [--show-chapters] \
  [--dir /path/to/Texts]


With pandas installed (or --pandas), output is a wider, nicely formatted table.

--show-chapters adds a compact chapters column (joined with |).

File naming & indexing

Filenames are NNN_slug_GUID.json (e.g., 001_makepath-introduction_XXXX.json) so they sort naturally.

If you don’t supply --index, the tool uses max existing index + 1.

GUID is stored uppercase internally and in filenames.

AppSettings.json behavior

Location: one directory up from ELGATO_PROMPTER_DIR.
Example:

~/Library/Application Support/Elgato/Camera Hub/
  AppSettings.json
  Texts/
    001_intro_<GUID>.json


Key: applogic.prompter.libraryList (a list of GUID strings)

On add: the GUID is appended (if not already present).

On del: matching GUIDs are removed.

Writes are atomic (temporary file then replace) to reduce corruption risk.

If AppSettings.json is missing or malformed, the tool recreates the needed structure.

Troubleshooting

“No prompts found.”
Ensure ELGATO_PROMPTER_DIR points to the Texts directory or pass --dir.

Pandas not installed (for fancy tables):

pipx inject elgato-prompter-text pandas
# or during install:
pipx install .[table]


Windows (CMD) env var:

set ELGATO_PROMPTER_DIR=%APPDATA%\Elgato\CameraHub\Texts

Uninstall
pipx uninstall elgato-prompter-text
# or
pip uninstall elgato-prompter-text
