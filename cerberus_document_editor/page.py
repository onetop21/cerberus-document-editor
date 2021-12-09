import urwid
import json
import re
import yaml_parser
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from collections.abc import Iterable
from validator import Validator
from widget import Widget, FlatButton
from model import ObjectModel

from debug import log

# Page
# -- JSON Data
# -- JSON Schema
# -- Show Editor Widgets
class Page(metaclass=ABCMeta):
    def __init__(self, name, hwnd=None, modal=False):
        self.__name = name
        self.__hwnd = hwnd
        self.__modal = modal
        self.__keymap = {}
        self.__data = {}

    @property
    def name(self):
        return self.__name

    @property
    def hwnd(self):
        return self.__hwnd

    @hwnd.setter
    def hwnd(self, hwnd):
        self.__hwnd = hwnd
    
    @property
    def keymap(self):
        return dict([(k, type('KeyMap', (), v)) for k, v in self.__keymap.items()])

    @property
    def json(self):
        return json.loads(json.dumps(self.__data))
    
    @json.setter
    def json(self, data):
        self.__data = data

    @property
    def is_modal(self):
        return self.__modal

    def __repr__(self):
        return json.dumps(self.__data)

    def register_keymap(self, k, desc, callback, enabled=True):
        self.__keymap[k] = {
            'description': desc,
            'callback': callback,
            'enabled': enabled
        }
    
    def unregister_keymap(self, k):
        if k in self.__keymap:
            del self.__keymap[k]

    def set_keymap(self, k, enable=True):
        if k in self.__keymap:
            self.__keymap[k]['enabled'] = enable

    def next(self, page):
        self.__hwnd.push(page)

    def close(self):
        self.__hwnd.pop()

    def render(self):
        self.__hwnd.redraw()

    def warning(self, message=None):
        self.hwnd.set_indicator(message)

    def on_change_focus(self):
        self.warning()

    @abstractmethod
    def on_page_result(self, page):
        ...

    @abstractmethod
    def on_update(self):
        ...

    @abstractmethod
    def on_draw(self):
        ...

    @abstractmethod
    def on_close(self):
        ...

class EditorPage(Page):
    def __init__(self, name, schema, document, sub_page=False):
        super().__init__(name)
        self.listbox_contents = []
        self.widget_map = {}
        validator = Validator(schema)
        self.json = {
            'document': validator.normalized_by_order(document) or document,
            'schema': schema
        }

        if sub_page:
            self.register_keymap('ctrl left', 'Back', lambda page: page.close())
    
    def __repr__(self):
        return json.dumps(self.json.get('document', {}))

    def add_column_number(self, label, desc=None, value=0.):
        log('add_column_number')
        return self.add_item(Widget.Edit.number(label, value), desc)

    def add_column_integer(self, label, desc=None, value=0):
        log('add_column_integer')
        return self.add_item(Widget.Edit.integer(label, value), desc)

    def add_column_str(self, label, desc=None, value=None, multiline=False):
        log('add_column_str')
        return self.add_item(Widget.Edit.text(label, value, multiline), desc)

    def add_column_object(self, label, desc=None, text='More...', callback=None):
        return self.add_item(Widget.button(label, text, callback or (lambda x: None)), desc)

    def add_column_dropdown(self, label, desc=None, items=[], default=None, callback=None):
        return self.add_item(Widget.dropdown(label, items, items.index(default)) if default else 0, desc)
        
    def add_column(self, label, desc=None, dtype='string', **kwargs):
        #, value=None, callback=None, multiline=False):
        if dtype in ['boolean', 'binary', 'date', 'datetime', 'list', 'set']:
            # bool, (bytes, bytearray), datetime.date, datetime.datetime, Collections.abc.Squence, set
            ...
        else:
            widget = None
            if dtype == 'number':
                return self.add_column_number(label, desc, kwargs.get('value', 0.0))
            elif dtype == 'integer':   # int
                return self.add_column_integer(label, desc, kwargs.get('value', 0))
            elif dtype == 'string':    # str
                return self.add_column_str(label, desc, kwargs.get('value', 0), kwargs.get('multiline', False))
            elif dtype == 'dict':      # dict
                return self.add_column_object(label, desc, kwargs.get('text', 'More...'), kwargs.get('callback', None))
            elif dtype == 'dropdown':   # options
                return self.add_column_dropdown(label, desc, kwargs.get('items', []), kwargs.get('default', 0), kwargs.get('callback', None))

    def add_item(self, widget, desc=None):
        ignore_react_list = [
            urwid.Button, FlatButton
        ]
        #self.listbox_contents.append(Widget.divider())
        if desc: self.listbox_contents.append(Widget.text(f'# {desc}', colorscheme='description'))
        self.listbox_contents.append(widget)
        inner_widget = Widget.unwrap_widget(widget)
            
        if not type(inner_widget) in ignore_react_list:
            signal = urwid.connect_signal(inner_widget, 'change', self.on_change)
        return inner_widget
   
    def clear_items(self):
        self.listbox_contents = []

    def on_draw(self):
        if len(self.listbox_contents):
            walker = urwid.SimpleListWalker(self.listbox_contents)
            urwid.connect_signal(walker, 'modified', self.on_change_focus)
            self._page_widget = urwid.ListBox(walker)
            return self._page_widget
        else:
            return urwid.Filler(
                urwid.Padding(
                    urwid.Text("Empty items.", align=urwid.CENTER),
                    align=urwid.CENTER
                ), valign=urwid.MIDDLE
            )

    def get_focus_widget(self):
        if hasattr(self, '_page_widget'):
            _ = self._page_widget.get_focus_widgets()
            return _[-1]

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

            # 여기서 validate하면 좋을 듯??!
            if '__root__' in schema:
                schema = schema['__root__']
                if schema.get('selector'):
                    selectable_kinds = [_.title() for _ in schema['selector']]
                    schema = schema['selector'][document['kind'].lower()]
                elif schema.get('valuesrules'):
                    valuesrules = schema
                    schema = dict([(key, schema['valuesrules']) for key in document])
                elif schema.get('type') == 'list':
                    is_list = True
                else:                
                    schema = schema['schema']
            
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
            else:                
                schema = schema['schema']

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
            for k in schema:
                if not k in doc:
                    appendable_items.append(k)
            if appendable_items:
                def callback(self):
                    self.next(PopupPage("Add new item", background=self.on_draw(), dtype='option', items=appendable_items))
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
                        self.hwnd.enable_warning("Cannot not remove immutable item(required or default item).")
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
                        doc['kind'],
                        callback=callback_generator(
                            key,
                            sub_schema,
                            value
                        )
                    )
                    self.widget_map[hash(widget)] = f'__{key}__'
                elif dtype in ['float', 'number']:       # float
                    value = value or 0.
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
                                {'type': 'dict'}, 
                                value
                            )
                        )
                        self.widget_map[hash(widget)] = key
            except Exception as e:
                raise e

    def on_close(self):
        self.next(PopupPage("Exit with Save", return_key='exit', background=self.on_draw(), dtype='option', items=['Yes', 'No', 'Cancel']))
        return True

class PopupPage(Page):
    def __init__(self, name, dtype='edit', return_key='popup', **kwargs):
        super().__init__(name, modal=True)
        self.listbox_contents = []
        self.dtype = dtype
        self.return_key = return_key
        self.validate=False
        self.bg_frame = kwargs.get('background', urwid.SolidFill(u'\N{MEDIUM SHADE}'))
        self.add_item(Widget.text(name.upper(), colorscheme='label'))
        self.add_item(Widget.divider())
        if dtype == 'edit':
            schema = kwargs.get('schema', None)
            self.validator = Validator(schema) if schema else None
            self.add_item(Widget.Edit.text())
            status_bar = Widget.text(colorscheme='stat')
            self.add_item(status_bar)
            self.status_bar = Widget.unwrap_widget(status_bar)
        elif dtype == 'option':
            self.items = kwargs.get('items', [])
            for item in self.items:
                self.add_item(Widget.button(None, item, lambda x: self.on_choose(x.label), colorschemes=('label', 'focus')))
        else:
            raise RuntimeError(f'Not Supported type. [{dtype}]')
        self.register_keymap('esc', 'Cancel', lambda page: page.on_cancel())
        self.register_keymap('enter', 'Add', lambda page: page.on_apply())

    def add_item(self, widget):
        log(widget)
        ignore_react_list = [
            urwid.Text, FlatButton, urwid.Divider
        ]
        self.listbox_contents.append(widget)
        inner_widget = Widget.unwrap_widget(widget)
        if not type(inner_widget) in ignore_react_list:
            signal = urwid.connect_signal(inner_widget, 'change', self.on_change)
        return inner_widget
   
    def clear_items(self):
        self.listbox_contents = []

    def on_draw(self):
        return urwid.Overlay(
            urwid.LineBox(urwid.ListBox(urwid.SimpleListWalker(self.listbox_contents))),
            self.bg_frame,
            align='center', width=('relative', 50), min_width=20,
            valign='middle', height=len(self.listbox_contents)+2, min_height=4
        )

    def on_page_result(self, page):
        self.render()

    def on_choose(self, value):
        self.json = {self.return_key: value}
        self.close()

    def on_apply(self):
        if self.validate:
            self.close()
        else:
            self.status_bar.set_text("Item is not valid.")

    def on_cancel(self):
        log('??')
        self.json = {}
        self.close()

    def on_change(self, widget, new_value):
        if self.validator and not self.validator.validate({'value': new_value}):
            def get_message(errors, stack=[]):
                message = []
                for error in errors:
                    if isinstance(error, dict):
                        for k, v in error.items():
                            stack.append(k)
                            message += get_message(v, stack)
                            stack.pop(-1)
                    elif isinstance(error, str):
                        message.append(f"{error}")
                        #message.append(f"{'.'.join(stack)}: {error}")
                return message
            error = ', '.join(get_message(self.validator.errors['__root__']))
            self.status_bar.set_text(error)
            self.validate=False
        else:
            self.json = {self.return_key: new_value}
            self.validate=True
            self.status_bar.set_text("")

    def on_update(self):
        ...

    def on_close(self):
        ...
