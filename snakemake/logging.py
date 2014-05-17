# -*- coding: utf-8 -*-

import logging as _logging
import platform
import time
import sys
import json
from multiprocessing import Lock

__author__ = "Johannes Köster"


class ColorizingStreamHandler(_logging.StreamHandler):
    _output_lock = Lock()

    BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
    RESET_SEQ = "\033[0m"
    COLOR_SEQ = "\033[%dm"
    BOLD_SEQ = "\033[1m"

    colors = {
        'WARNING': YELLOW,
        'INFO': GREEN,
        'DEBUG': BLUE,
        'CRITICAL': RED,
        'ERROR': RED
    }

    def __init__(self, nocolor=False, stream=sys.stderr, timestamp=False):
        super().__init__(stream=stream)
        self.nocolor = nocolor or not self.is_tty or platform.system() == 'Windows'
        self.timestamp = timestamp

    @property
    def is_tty(self):
        isatty = getattr(self.stream, 'isatty', None)
        return isatty and isatty()

    def emit(self, record):
        with self._output_lock:
            try:
                self.format(record)  # add the message to the record
                self.stream.write(self.decorate(record))
                self.stream.write(getattr(self, 'terminator', '\n'))
                self.flush()
            except BrokenPipeError as e:
                raise e
            except (KeyboardInterrupt, SystemExit):
                # ignore any exceptions in these cases as any relevant messages have been printed before
                pass
            except Exception as e:
                self.handleError(record)

    def decorate(self, record):
        message = [record.message]
        if self.timestamp:
            message.insert(0, "[{}] ".format(time.asctime()))
        if not self.nocolor and record.levelname in self.colors:
            message.insert(0, self.COLOR_SEQ % (30 + self.colors[record.levelname]))
            message.append(self.RESET_SEQ)
        return "".join(message)


class Logger:
    def __init__(self):
        self.logger = _logging.getLogger(__name__)
        self.handler = self.console_handler
        self.stream_handler = None
        self.printshellcmds = False
        self.printreason = False
    
    def set_stream_handler(self, stream_handler):
        if self.stream_handler is not None:
            self.logger.removeHandler(self.stream_handler)
        self.stream_handler = stream_handler
        self.logger.addHandler(stream_handler)

    def set_level(self, level):
        self.logger.setLevel(level)

    def info(self, msg):
        self.handler(dict(level="info", msg=msg))

    def debug(self, msg):
        self.handler(dict(level="debug", msg=msg))

    def error(self, msg):
        self.handler(dict(level="error", msg=msg))

    def progress(self, done=None, total=None):
        self.handler(dict(level="progress", done=done, total=total))

    def resources_info(self, msg):
        self.handler(dict(level="resources_info", msg=msg))

    def run_info(self, msg):
        self.handler(dict(level="run_info", msg=msg))

    def job_info(self, **msg):
        msg["level"] = "job_info"
        self.handler(msg)

    def d3dag(self, **msg):
        msg["level"] = "d3dag"
        self.handler(msg)

    def console_handler(self, msg):
        """The default snakemake log handler.
        
        Prints the output to the console.
        
        Args:
            msg (dict):     the log message dictionary
        """
        def job_info(msg):
            def format_item(item, omit=None, valueformat=str):
                value = msg[item]
                if value != omit:
                    return "\t{}: {}".format(item, valueformat(value))
                    
            yield "{}rule {}:".format("local" if msg["local"] else "", msg["name"])
            for item in "input output".split():
                fmt = format_item(item, omit=[], valueformat=", ".join)
                if fmt != None:
                    yield fmt
            singleitems = ["log"]
            if self.printreason:
                singleitems.append("reason")
            for item in singleitems:
                fmt = format_item(item, omit=None)
                if fmt != None:
                    yield fmt
            for item, omit in zip("priority threads".split(), [0,1]):
                fmt = format_item(item, omit=omit)
                if fmt != None:
                    yield fmt
            resources = format_resources(msg["resources"])
            if resources:
                yield "\tresources: " + resources

        level = msg["level"]
        if level == "info":
            self.logger.warning(msg["msg"])
        elif level == "error":
            self.logger.error(msg["msg"])
        elif level == "debug":
            self.logger.debug(msg["msg"])
        elif level == "resources_info":
            self.logger.warning(msg["msg"])
        elif level == "run_info":
            self.logger.warning(msg["msg"])
        elif level == "progress" and not self.quiet:
            done = msg["done"]
            total = msg["total"]
            self.logger.info("{} of {} steps ({:.0%}) done".format(done, total, done / total))
        elif level == "job_info":
            if not self.quiet:
                if msg["msg"] is not None:
                    self.logger.info(msg["msg"])
                else:
                    self.logger.info("\n".join(job_info(msg)))
            if self.printshellcmds and msg["shellcmd"]:
                self.logger.info(msg["shellcmd"])
        elif level == "d3dag":
            json.dumps({"nodes": msg["nodes"], "links": msg["links"]})


def format_resources(resources, omit_resources="_cores _nodes".split()):
    return ", ".join("{}={}".format(name, value) for name, value in resources.items() if name not in omit_resources)


def format_resource_names(resources, omit_resources="_cores _nodes".split()):
    return ", ".join(name for name in resources if name not in omit_resources)


logger = Logger()


def setup_logger(handler=None, quiet=False, printshellcmds=False, printreason=False, nocolor=False, stdout=False, debug=False, timestamp=False):
    if handler is not None:
        logger.handler = handler
    stream_handler = ColorizingStreamHandler(
        nocolor=nocolor, stream=sys.stdout if stdout else sys.stderr,
        timestamp=timestamp
    )
    logger.set_stream_handler(stream_handler)
    logger.set_level(_logging.DEBUG if debug else _logging.INFO)
    logger.quiet = quiet
    logger.printshellcmds = printshellcmds
    logger.printreason = printreason
