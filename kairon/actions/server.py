from tornado.ioloop import IOLoop
from tornado.web import Application
from tornado.httpserver import HTTPServer
from tornado.options import parse_command_line
from kairon.shared.tornado.handlers.index import IndexHandler
from .handlers.action import ActionHandler
from ..shared.utils import Utility
from loguru import logger
from mongoengine import connect
from os import getenv
Utility.load_environment()


def make_app():
    return Application([
        (r"/", IndexHandler),
        (r"/webhook", ActionHandler),
    ], compress_response=True, debug=False)


if __name__ == "__main__":
    connect(**Utility.mongoengine_connection())
    app = make_app()
    Utility.initiate_tornado_apm_client(app)
    parse_command_line()
    server = HTTPServer(app)
    server.bind(5055)
    server.start(num_processes=int(getenv("WEB_CONCURRENCY", "1")))
    IOLoop.current().start()
    logger.info("Server Started")