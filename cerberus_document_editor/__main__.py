import sys
import os
import argparse
import json
import yaml_parser
import cerberus_document_editor as cde

APP_NAME = 'Cerberus Document Editor'
DESCRIPTION='Document Editor for Cerberus Schema.'
parser = argparse.ArgumentParser(description=DESCRIPTION)
parser.add_argument('-v', '--version', action='version', version=cde.__version__)
parser.add_argument('-s', '--schema', metavar='JSON_FILENAME', type=str, default='.schema.yaml', help='Select external schema file.')
parser.add_argument('document', metavar='FILENAME', type=str, help='Filename to edit.')

def exit_with_message(message, exitcode=1):
    print(message, file=sys.stderr)
    sys.exit(exitcode)

if __name__ == '__main__':
    args = parser.parse_args()

    if not os.path.exists(args.schema):
        exit_with_message('Cannot find schema file. [args.schema]')
    schema_ext = os.path.splitext(args.schema)[1]

    with open(args.schema) as f:
        if schema_ext.lower() in ['.yaml', '.yml']:
            schema = yaml_parser.load(f)
        elif schema_ext.lower() == '.json':
            schema = json.load(f)
        else:
            exit_with_message('Not support schema file type.')

    doc_ext = os.path.splitext(args.document)[1]
    if not doc_ext.lower() in ['.yaml', '.yml', '.json']:
        exit_with_message('Not support document file type.')
    if os.path.exists(args.document):
        with open(args.document) as f:
            if doc_ext.lower() in ['.yaml', '.yml']:
                document = yaml_parser.load(f)
            elif doc_ext.lower() == '.json':
                document = json.load(f)
            else:
                exit_with_message('Cannot support schema file type.')
    else:
        document = {}

    app = cde.MainWindow(APP_NAME,
        palette=[
            ('header','white,bold', 'black', 'bold'),
            ('footer','white,bold', 'black', 'bold'),
            ('body','white', 'dark gray', ''),
            ('label','white,bold', 'dark gray', 'bold'),
            ('description','yellow,bold', 'dark gray'),
            ('edit', 'white', 'dark gray'),
            ('combo', 'light gray', 'black'),
            ('focus', 'black', 'white', 'bold'),
            ('warn', 'black', 'light red', 'bold'),
            ('stat', 'dark red,bold', 'dark gray'),
        ]
    )
    modified = app.run(cde.EditorPage(os.path.basename(args.document), schema, document))
    if modified:
        with open(args.document, 'wt') as f:
            if doc_ext in ['.yaml', 'yml']:
                f.write(yaml_parser.dump(modified))
            elif doc_ext in ['.json']:
                f.write(json.dumps(modified, indent=2))
            else:
                print(f'Cannot support file format.', file=sys.stderr)
