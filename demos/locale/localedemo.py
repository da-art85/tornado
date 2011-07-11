#!/usr/bin/env python

import os
import tornado.locale

from tornado.ioloop import IOLoop
from tornado.options import define, options, parse_command_line
from tornado.web import RequestHandler, Application

define('port', default=8888)
define('debug', default=False)

class FormHandler(RequestHandler):
    def get(self):
        self.render("form.html")

    def get_user_locale(self):
        return tornado.locale.get(self.get_argument("locale", "en_US"))

def main():
    parse_command_line()
    tornado.locale.load_translations(
        os.path.join(os.path.dirname(__file__), "translations"))

    app = Application(
        [
            ("/", FormHandler),
            ],
        template_path=os.path.join(os.path.dirname(__file__), "templates"),
        debug=options.debug,
        )
    app.listen(options.port)
    IOLoop.instance().start()
    

if __name__ == '__main__':
    main()
