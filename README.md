# Elgato Prompter Text Command Line Interface (CLI)

A tiny cross-platform CLI to manage Elgato Prompter script JSON files.

Inspired by https://github.com/spieldbergo/elgato_prompter_text_importer

- Integrates with Pydantic-AI to generate prompts
- Tries to automatically shutdown and restart Camera Hub app (yes this is a hack)
- Add new prompter scripts from files from the command line


**TOTALLY EXPERIMENTAL**

**MOSTLY VIBE-CODED :()**

## Features

- **add** – create a new JSON prompt file (auto GUID, auto index unless you supply one)
- **del** – delete prompt file(s) by GUID, friendly name, or filename
- **ls** – list prompts as a clean table (uses pandas if installed)
- **gen** - generate prompts using an LLM via Pydantic-AI

## Installation
Requirements

- Python 3.9+
- Pydantic-AI  (recommend to include examples for reference)
```pip install pydantic-ai[examples]```
(Optional) pandas (used by ls for pretty tables)

Clone the code from the repo and run install with pip (recommended)

##### Get the code
```bash
git clone https://github.com/brendancol/elgato_prompter_text_cli.git
cd elgato_prompter_text_cli
pip install -e .            # minimal install
```

This exposes the console script:

```bash
elgato-prompter-text --help
```

##### Configure the scripts directory

The tool needs to know where your Texts directory is.

You can provide it in two ways:

Environment variable: `ELGATO_PROMPTER_DIR`

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
