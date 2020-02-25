from createhero.app import CreateHeroAPI, TaskExecutor

from adhero_utils.handlers import GenericHandler

from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
import tornado.netutil
import tornado.process
import logging
import argparse
import multiprocessing as mp
import os
import base64
# from datadog import initialize

# logging init
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
if root_logger.hasHandlers():
    root_logger.handlers.clear()

handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)
root_logger.addHandler(handler)

# start the server
def main():
    # initialize DogStatsD
    # dd_options = {
    #     'statsd_socket_path' : '/var/run/datadog/dsd.socket'
    # }
    #
    # initialize(**dd_options)

    logger = logging.getLogger('CreateHeroAPI')
    logging.getLogger('tornado.access').setLevel(logging.WARN)

    working_directory = os.path.dirname(os.path.abspath(__file__))
    socket_external = tornado.netutil.bind_sockets(8888)

    with mp.Manager() as mgr:
        settings = {}
        # set internal url everywhere
        settings['documentation'] = os.path.dirname(os.path.abspath(__file__)) + '/swagger.yml'
        # create shared communication dict
        settings['task_queue'] = mgr.Queue()
        settings['tasks'] = mgr.dict()
        settings['working_directory'] = working_directory

        #fork to child processes
        pid = tornado.process.fork_processes(2)
        #construct the app
        app = AdHeroAPI()
        #pass the settings
        app.settings.update(settings)
        server = HTTPServer(app)
        server.add_sockets(socket_external)
        # start services in separate processes
        if pid != 1:
            task_executor = TaskExecutor(settings['task_queue'])
            task_executor.start()
        IOLoop.current().start()

if __name__ == '__main__':
   main()
