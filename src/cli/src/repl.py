#!/usr/bin/env python
#+
# Copyright 2014 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

import sys
import os
import glob
import argparse
import shlex
import imp
import logging
import struct
import fcntl
import platform
import termios
import config
import json
import gettext
import signal
import traceback
from descriptions import events, tasks
from namespace import RootNamespace
from output import output_lock, output_msg
from dispatcher.client import Client, ClientError
from commands import ExitCommand, PrintenvCommand, SetenvCommand


if platform.system() == 'Darwin':
    import gnureadline as readline
else:
    import readline


DEFAULT_CONFIGFILE = '/usr/local/etc/middleware.conf'
DEFAULT_RC = os.path.expanduser('~/.freenascli.conf')
t = gettext.translation('freenas-cli', fallback=True)
_ = t.ugettext


class VariableStore(object):
    class Variable(object):
        def __init__(self, default, type, choices=None):
            self.default = default
            self.type = type
            self.choices = choices
            self.value = default

        def set(self, value):
            try:
                if self.type == int:
                    value = int(value)
            except ValueError:
                raise

            if self.choices is not None and value not in self.choices:
                raise ValueError(_("Value not on the list of possible choices"))

    def __init__(self):
        self.variables = {
            'output-format': self.Variable('ascii', str, ['ascii', 'json']),
            'datetime-format': self.Variable('natural', str),
            'language': self.Variable(os.environ['LANG'], str),
            'prompt': self.Variable('{host}:{path}>', str),
            'timeout': self.Variable(10, int),
            'show-events': self.Variable(True, bool)
        }

    def load(self, filename):
        pass

    def save(self, filename):
        pass

    def get(self, name):
        return self.variables[name].value

    def get_all(self):
        for name, var in self.variables.items():
            yield (name, var.value)

    def set(self, name, value):
        self.variables[name].set(value)


class Context(object):
    def __init__(self):
        self.hostname = None
        self.connection = Client()
        self.ml = None
        self.logger = logging.getLogger('cli')
        self.plugin_dirs = []
        self.plugins = {}
        self.variables = VariableStore()
        self.root_ns = RootNamespace()
        self.event_masks = ['*']
        config.instance = self

    def start(self):
        self.discover_plugins()
        self.connect()

    def connect(self):
        self.connection.on_event(self.print_event)
        self.connection.on_error(self.connection_error)
        self.connection.connect(self.hostname)

    def read_config_file(self, file):
        try:
            f = open(file, 'r')
            data = json.load(f)
            f.close()
        except (IOError, ValueError):
            raise

        if 'cli' not in data:
            return

        if 'plugin-dirs' not in data['cli']:
            return

        if type(data['cli']['plugin-dirs']) != list:
            return

        self.plugin_dirs += data['cli']['plugin-dirs']

    def discover_plugins(self):
        for dir in self.plugin_dirs:
            self.logger.debug(_("Searching for plugins in %s"), dir)
            self.__discover_plugin_dir(dir)

    def login_plugins(self):
        for i in self.plugins.values():
            if hasattr(i, '_login'):
                i._login(self)

    def __discover_plugin_dir(self, dir):
        for i in glob.glob1(dir, "*.py"):
            self.__try_load_plugin(os.path.join(dir, i))

    def __try_load_plugin(self, path):
        if path in self.plugins:
            return

        self.logger.debug(_("Loading plugin from %s"), path)
        plugin = imp.load_source('plugin', path)
        if hasattr(plugin, '_init'):
            plugin._init(self)
            self.plugins[path] = plugin

    def __try_reconnect(self):
        pass

    def attach_namespace(self, path, ns):
        splitpath = path.split('/')
        ptr = self.root_ns

        for n in splitpath[1:-1]:
            if n not in ptr.namespaces().keys():
                self.logger.warn(_("Cannot attach to namespace %s"), path)
                return

            ptr = ptr.namespaces()[n]

        ptr.register_namespace(splitpath[-1], ns)

    def connection_error(self, event):
        if event == ClientError.CONNECTION_CLOSED:
            self.__try_reconnect()
            return

    def print_event(self, event, data):
        self.ml.blank_readline()
        output_lock.acquire()
        output_msg(events.translate(event, data))
        output_lock.release()
        self.ml.restore_readline()

    def submit_task(self, name, *args):
        return self.connection.call_sync('task.submit', name, args)


class PathItem(object):
    def __init__(self, name, ns):
        self.name = name
        self.ns = ns


class MainLoop(object):
    builtin_commands = {
        'exit': ExitCommand(),
        'setenv': SetenvCommand(),
        'printenv': PrintenvCommand()
    }

    def __init__(self, context):
        self.context = context
        self.root_path = [PathItem(self.context.hostname, self.context.root_ns)]
        self.path = self.root_path[:]
        self.namespaces = []
        self.connection = None

    def __get_prompt(self):
        return '/'.join([x.name for x in self.path]) + '> '

    def cd(self, name, ns):
        self.path.append(PathItem(name, ns))

    @property
    def cwd(self):
        return self.path[-1]

    def tokenize(self, line):
        args = []
        kwargs = {}
        tokens = shlex.split(line, posix=False)

        for t in tokens:
            if t[0] == '"' and t[-1] == '"':
                t = t[1:-1]
                args.append(t)
                continue

            if '=' in t:
                key, eq, value = t.partition('=')
                if value[0] == '"' and value[-1] == '"':
                    value = value[1:-1]

                kwargs[key] = value
                continue

            args.append(t)

        return args, kwargs

    def repl(self):
        readline.parse_and_bind('tab: complete')
        readline.set_completer(self.complete)
        while True:
            line = raw_input(self.__get_prompt()).strip()

            if len(line) == 0:
                continue

            if line[0] == '/':
                self.path = self.root_path[:]
                line = line[1:]

            if line == '..':
                if len(self.path) > 1:
                    del self.path[-1]
                    continue

            tokens, kwargs = self.tokenize(line)
            oldpath = self.path[:]

            while tokens:
                token = tokens.pop(0)
                nsfound = False
                cmdfound = False

                if token in self.builtin_commands.keys():
                    self.builtin_commands[token].run(self.context, tokens, kwargs)
                    break

                try:
                    for name, ns in self.cwd.ns.namespaces().items():
                        if token == name:
                            self.cd(token, ns)
                            nsfound = True
                            break

                    for name, cmd in self.cwd.ns.commands().items():
                        if token == name:
                            output_lock.acquire()
                            cmd.run(self.context, tokens, kwargs)
                            cmdfound = True
                            output_lock.release()
                            break

                except Exception, err:
                    print 'Error: {0}'.format(str(err))
                    traceback.print_exc()
                    break
                else:
                    if not nsfound and not cmdfound:
                        print _("Command not found! Type \"?\" for help.")
                        break

                    if cmdfound:
                        self.path = oldpath
                        break

    def complete(self, text, state):
        choices = self.cwd.ns.namespaces().keys() + self.cwd.ns.commands().keys() + self.builtin_commands.keys()
        options = [i for i in choices if i.startswith(text)]
        if state < len(options):
            return options[state]
        else:
            return None

    def blank_readline(self):
        rows, cols = struct.unpack('hh', fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, '1234'))
        text_len = len(readline.get_line_buffer()) + 2
        sys.stdout.write('\x1b[2K')
        sys.stdout.write('\x1b[1A\x1b[2K' * (text_len / cols))
        sys.stdout.write('\x1b[0G')

    def restore_readline(self):
        sys.stdout.write(self.__get_prompt() + readline.get_line_buffer().rstrip())
        sys.stdout.flush()


def main():
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument('hostname', metavar='HOSTNAME', default='127.0.0.1')
    parser.add_argument('--config', metavar='CONFIGFILE', default=DEFAULT_CONFIGFILE)
    parser.add_argument('-c', metavar='COMMANDS')
    parser.add_argument('-l', metavar='LOGIN')
    parser.add_argument('-p', metavar='PASSWORD')
    parser.add_argument('-D', metavar='DEFINE', action='append')
    args = parser.parse_args()
    context = Context()
    context.hostname = args.hostname
    context.read_config_file(args.c)
    context.start()

    if args.l:
        context.connection.login_user(args.l, args.p)
        context.connection.subscribe_events('*')
        context.login_plugins()

    ml = MainLoop(context)
    context.ml = ml
    ml.repl()


if __name__ == '__main__':
    main()