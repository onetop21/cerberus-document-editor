# cerberus-document-editor
Document Editor for Cerberus Schema (Urwid)

[![Upload Python Package](https://github.com/onetop21/cerberus-document-editor/actions/workflows/python-publish.yml/badge.svg?branch=main)](https://github.com/onetop21/cerberus-document-editor/actions/workflows/python-publish.yml)

## How to install
```bash
pip install cerberus-document-editor
```

## How to run
```bash
python -m cerberus-document-editor --help

usage: cerberus_document_editor [-h] [-v] [-s JSON_FILENAME] FILENAME

Document Editor for Cerberus Schema.

positional arguments:
  FILENAME              Filename to edit.

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -s JSON_FILENAME, --schema JSON_FILENAME
                        Select external schema file.
```

## Default Schema Filename
Cerberus document editor is set default schema filename to .schema.yaml.
This editor is supporting JSON and YAML file type for document and schema.
You can refer below file.
[.schema.yaml](https://raw.githubusercontent.com/onetop21/cerberus-document-editor/main/.schema.yaml)
