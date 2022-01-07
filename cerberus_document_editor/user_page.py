import urwid
import json
import re
from cerberus_document_editor import yaml_parser
from collections import OrderedDict
from .validator import Validator
from .widget import Widget, FlatButton
from .page import ListPage, PopupPage
from .debug import log

def cerberus_error(errors, with_path=False):
    def get_message(errors, stack=[]):
        message = []
        if isinstance(errors, str):
            if with_path:
                message.append(f"{'.'.join(filter(None, stack))}: {errors}")
            else:
                message.append(f"{errors}")
        elif isinstance(errors, dict):
            for k, v in errors.items():
                stack.append(str(k))
                message += get_message(v, stack)
                stack.pop(-1)
        elif isinstance(errors, list):
            for item in errors:
                message += get_message(item, stack)
        return message
    if '__root__' in errors:
        return ', '.join(get_message(errors['__root__']))
    else:
        return ', '.join(get_message(errors))

class EditorPage(ListPage):
    def __init__(self, name, schema, document, sub_page=False):
        super().__init__(name, sub_page=sub_page)
        self.widget_map = {}
        log(f'Schema: {schema}')
        validator = Validator(schema, purge_unknown=True)
        self.json = {
            'document': validator.normalized_by_order(document) or document,
            'schema': schema
        }

    def __repr__(self):
        return json.dumps(self.json.get('document', {}))

    def on_page_result(self, page):
        if page.json:
            if page.json.get('popup', None) is not None:
                key = page.json.get('popup')
                if key:
                    body = self.json
                    body['document'][key] = None
                    self.json = body
                    self.hwnd.modified()
                self.render()
            elif page.json.get('exit', None) is not None:
                key = page.json.get('exit')
                if key.lower() == 'yes':
                    self.hwnd.destroy()
                elif key.lower() == 'no':
                    self.hwnd.destroy(False)
                elif key.lower() == 'cancel':
                    ...
                self.render()
            else:
                data = self.json
                document = data['document']
                if isinstance(page.json['document'], list):
                    document[page.name] = list(filter(None, page.json['document']))
                elif isinstance(page.json['document'], dict):
                    document[page.name] = dict(filter(lambda x: x[1] is not None, page.json['document'].items()))
                else:
                    document[page.name] = page.json['document']
                if self.json != data:
                    self.json = data
                    self.hwnd.modified()
                self.render()

    def on_change(self, widget, new_value):
        def casting(value):
            if isinstance(widget, urwid.IntEdit):
                return int(f"0{value}")
            if isinstance(widget, urwid.numedit.FloatEdit):
                return float(f"0{value}")
            return value
        new_value = casting(new_value)

        key = self.widget_map.get(hash(widget))
        pattern = re.compile(r'^__(.*)__$')
        matched = pattern.match(str(key))
        if matched:
            key = matched.group(1)
            if key in ['kind']:
                data = self.json
                schema = data['schema']
                document = data['document']
                document[key] = new_value
                validator = Validator(schema, purge_unknown=True)
                data['document'] = validator.normalized_by_order(document)
                if self.json != data:
                    self.json = data
                    self.hwnd.modified()
                self.render()
        else:
            data = self.json
            document = data['document']
            schema = data['schema']

            # # 여기서 validate하면 좋을 듯??!
            # if '__root__' in schema:
            #     schema = schema['__root__']
            #     if schema.get('selector'):
            #         selectable_kinds = [_.title() for _ in schema['selector']]
            #         schema = schema['selector'][document['kind'].lower()]
            #     elif schema.get('valuesrules'):
            #         valuesrules = schema
            #         schema = dict([(key, schema['valuesrules']) for key in document])
            #     elif schema.get('type') == 'list':
            #         is_list = True
            #     else:                
            #         schema = schema['schema']
            
            show_warning = False
            item_schema = schema.get(key)
            if item_schema:
                regex = item_schema.get('regex')
                if regex:
                    matcher = re.compile(regex)
                    if not matcher.match(new_value):
                        show_warning = True
            if show_warning:
                self.warning(f"value does not match regex '{regex}'")
            else:
                self.warning()
                document[key] = new_value

            if self.json != data:
                self.json = data
                self.hwnd.modified()

    def on_update(self):
        doc = self.json['document']
        schema = self.json['schema']

        is_list = False
        selectable_kinds = None
        valuesrules = None
        if '__root__' in schema:
            schema = schema['__root__']
            if schema.get('selector'):
                selectable_kinds = [_.title() for _ in schema['selector']]
                schema = schema['selector'][doc['kind'].lower()]
            elif schema.get('valuesrules'):
                valuesrules = schema
                schema = dict([(key, schema['valuesrules']) for key in doc])
            elif schema.get('type') == 'list':
                is_list = True
            elif 'schema' in schema:                
                schema = schema['schema']
            else:
                schema = {}

        if valuesrules:
            def callback(self):
                schema = {
                    '__root__': {
                        'schema': {
                            'value': valuesrules.get('keysrules', {'type': 'string'})
                        }
                    }
                }
                self.next(PopupPage("Add new item", background=self.on_draw(), schema=schema))
            self.register_keymap('ctrl n', 'Add new item', callback)
        elif is_list:
            log('Doc is', self.json['document'])
            def callback(self):
                data = self.json
                document = data['document']
                sub_type = schema['schema']['type']
                log('before', document)
                if sub_type in ['string']:
                    document.append("")
                elif sub_type in ['integer']:
                    document.append(0)
                elif sub_type in ['float', 'number']:
                    document.append(.0)
                elif sub_type in ['list', 'dict']:
                    validator = Validator({'__root__': schema['schema']})
                    log({'__root__': schema['schema']})
                    document.append(validator.normalized())
                self.json = data
                log('after', document)
                self.render()
            self.register_keymap('ctrl n', 'Add new item', callback)
        else:
            appendable_items = []
            for k, v in schema.items():
                if not k in doc:
                    if 'description' in v:
                        appendable_items.append((k, v['description']))
                    else:
                        appendable_items.append(k)
            if appendable_items:
                def callback(self):
                    self.next(PopupPage("Add new item", background=self.on_draw(), ptype='select', items=appendable_items))
                self.register_keymap('ctrl n', 'Add new item', callback)
            else:
                self.unregister_keymap('ctrl n')

        deletable_items = []
        if len(doc):
            def delete_callback(self):
                    widget = self.get_focus_widget()
                    key = self.widget_map[hash(Widget.unwrap_widget(widget))]
                    if key in deletable_items:
                        data = self.json
                        log(key, type(key))
                        document = data['document']
                        del document[key]
                        self.json = data
                        self.render()
                    else:
                        self.warning("Cannot not remove immutable item(required or default item).")
            if is_list:
                self.register_keymap('ctrl d', 'Delete item', delete_callback)
            else:
                for k, v in schema.items():
                    if not v.get('required', False) and not v.get('default', None):
                        deletable_items.append(k)
                self.register_keymap('ctrl d', 'Delete item', delete_callback)

        def ellipsis(text, max_w=60, max_h=10):
            def cols(rows):
                output = []
                for row in rows:
                    if len(row) > max_w:
                        output.append(row[:max_w-3]+'...')
                    else:
                        output.append(row)
                return output
            rows = text.strip('\n').split('\n')
            if len(rows) > max_h:
                return '\n'.join(cols(rows[:max_h-1]+['...']))
            else:
                return '\n'.join(cols(rows))

        def callback_generator(name, schema, doc):
            def callback(key):
                try:
                    page = EditorPage(
                        name, 
                        json.loads(json.dumps(schema)), # deepcopy
                        json.loads(json.dumps(doc)),    # deepcopy
                        True,
                    )
                except KeyError as e:
                    if 'kind' in doc:
                        del doc['kind']
                    page = EditorPage(
                        name, 
                        json.loads(json.dumps(schema)), # deepcopy
                        json.loads(json.dumps(doc)),    # deepcopy
                        True,
                    )
                self.next(page)
            return callback
        
        self.clear_items()
        for key, value in (enumerate(doc) if is_list else OrderedDict(doc).items()):
            try:
                if is_list:
                    sub_schema = json.loads(json.dumps(schema['schema']))
                else:
                    sub_schema = json.loads(json.dumps(schema[key]))   # deepcopy
                dtype = sub_schema.get('type', 'string')
                dtype = dtype[0] if isinstance(dtype, list) else dtype
                desc = sub_schema.get('description', None)

                if selectable_kinds and key == 'kind':
                    widget = self.add_column_dropdown(key, desc, 
                        selectable_kinds,
                        doc['kind']
                    )
                    self.widget_map[hash(widget)] = f'__{key}__'
                elif sub_schema.get('allowed'):
                    allowed_list = sub_schema.get('allowed')
                    widget = self.add_column_dropdown(key, desc, 
                        allowed_list,
                        doc[key] if doc[key] in allowed_list else allowed_list[0]
                    )
                    self.widget_map[hash(widget)] = key
                elif dtype in ['float', 'number']:       # float
                    value = value or .0
                    widget = self.add_column_number(key, desc, value)
                    self.widget_map[hash(widget)] = key
                elif dtype in ['integer']:             # integer
                    value = value or 0
                    widget = self.add_column_integer(key, desc, value)
                    self.widget_map[hash(widget)] = key
                elif dtype in ['string']:
                    value = value or ""
                    widget = self.add_column_str(key, desc, value, sub_schema.get('multiline', False))
                    self.widget_map[hash(widget)] = key
                elif dtype in ['list']:
                    value = value or []
                    widget = self.add_column_object(key, desc, text=ellipsis(yaml_parser.dump(value)),
                        callback=callback_generator(
                            key,
                            {'__root__': sub_schema},
                            value
                        )
                    )
                    self.widget_map[hash(widget)] = key
                elif dtype in ['dict']:                 # Object
                    value = value or {}
                    if 'valuesrules' in sub_schema:
                        widget = self.add_column_object(key, desc, text=ellipsis(yaml_parser.dump(value)),
                            callback=callback_generator(
                                key,
                                {'__root__': sub_schema},
                                value
                            )
                        )
                        self.widget_map[hash(widget)] = key
                    elif 'schema' in sub_schema:
                        widget = self.add_column_object(key, desc, text=ellipsis(yaml_parser.dump(value)), 
                            callback=callback_generator(
                                key,
                                sub_schema['schema'], 
                                value
                            )
                        )
                        self.widget_map[hash(widget)] = key
                    elif 'selector' in sub_schema:
                        widget = self.add_column_object(key, desc, text=ellipsis(yaml_parser.dump(value)), 
                            callback=callback_generator(
                                key,
                                {'__root__': sub_schema},
                                value
                            )
                        )
                        self.widget_map[hash(widget)] = key
                    else:
                        widget = self.add_column_object(key, desc, text=ellipsis(yaml_parser.dump(value)), 
                            callback=callback_generator(
                                key,
                                {'__root__': {'type': 'dict', 'valuesrules': {'type': 'string'}}}, 
                                value
                            )
                        )
                        self.widget_map[hash(widget)] = key
            except Exception as e:
                raise e

        try:
            validator = Validator(schema)
        except:
            validator = Validator({'__root__': schema})
        if not validator.validate(doc):
            self.warning(cerberus_error(validator.errors, with_path=True))

    def on_close(self):
        self.next(PopupPage("Exit with Save", return_key='exit', background=self.on_draw(), ptype='select', items=['Yes', 'No', 'Cancel']))
        return True
