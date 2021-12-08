import urwid
import json
from interrupt_handler import InterruptHandler

from debug import log

# Main Editor
# -- Page Stack (with Header)
# -- Show Top Page
# -- Serialize (JSON from Page)
class MainWindow:
    def __init__(self, name, palette=[]):
        self.name = name
        self.stack = []
        self.palette = palette
        self.__header_stack = urwid.Columns([], dividechars=2)
        self.__header = urwid.Columns([(len(name), urwid.Text(name.strip(' .').upper())), self.__header_stack], dividechars=5)  
        self.__footer_list = urwid.Columns([], dividechars=1)
        self.__footer = urwid.Pile([self.__footer_list])
        self.__body = urwid.AttrWrap(
            urwid.Filler(
                urwid.Padding(
                    urwid.Text(f":: {name} ::")
                    , "center"
                ), "middle"
            ), "body"
        )
        self.__view = urwid.Frame(
            urwid.AttrWrap(self.__body, 'body'),
            header=urwid.AttrWrap(self.__header, 'header'),
            footer=urwid.AttrWrap(self.__footer, 'footer')
        )

    def enable_warning(self, message):
        self.__footer = urwid.Pile([urwid.AttrWrap(urwid.Text(message), "warn"), self.__footer_list])
        self.__view.set_footer(urwid.AttrWrap(self.__footer, 'footer'))

    def disable_warning(self):
        self.__footer = urwid.Pile([self.__footer_list])
        self.__view.set_footer(urwid.AttrWrap(self.__footer, 'footer'))

    def push(self, page):
        page.hwnd = self
        self.stack.append(page)
        self.redraw()

    def pop(self):
        if len(self.stack) > 1:
            page = self.stack.pop()
            self.stack[-1].on_page_result(page)
        self.redraw()

    @property
    def front_page(self):
        return json.loads(str(self.stack[0]))

    def redraw(self):
        if len(self.stack) > 0:
            page = self.stack[-1]
            page.on_update()
            self.__header_stack.contents = [
                (urwid.Text('> ' + name), ('pack', len(name)+2, False)) if i > 0 else \
                (urwid.Text(name), ('pack', len(name), False)) \
                for i, name, _ in [(i, f"[{_.name}]" if isinstance(_.name, int) else f"{_.name}", _) for i, _ in enumerate(self.stack)]
            ]
            self.__footer_list.contents = [(urwid.Text(_.description), ('weight', 1, False)) for _ in page.keymap.values()]
            if not page.is_modal:
                self.__footer_list.contents += [(urwid.Text("Ctrl+X: Exit"), ('weight', 1, False))]
            self.__body.w = page.on_draw()

    def input_handler(self, k):
        if len(self.stack):
            page = self.stack[-1]
            keymap = page.keymap
            if k in keymap:
                keymap[k].callback(page)
            elif k in ['ctrl x'] and not page.is_modal:
                if not self.stack[-1].on_close():
                    self.destroy()
        else:
            self.destroy()

    def destroy(self, save_exit=True):
        while len(self.stack) > 1:
            self.stack[-1].close()
        self.save_exit = save_exit
        raise urwid.ExitMainLoop()

    def run(self, start_page):
        self.push(start_page)
        with InterruptHandler(lambda: True):
            self.loop = urwid.MainLoop(self.__view, self.palette,
                unhandled_input=self.input_handler, pop_ups=True)
            self.loop.run()
        if getattr(self, 'save_exit'):
            return self.front_page
