from tornado.web import Application
from tornado.ioloop import PeriodicCallback
import createhero.handler as h
import logging

class CreateHeroAPI(Application):

    def __init__(self):
        super().__init__()
        self.log = logging.getLogger('CreateHeroAPI')
        self.add_routes()
        self.log.info('CreateHero API ready')

    def add_routes(self):
        route_list = [
                (r"/video/flip/tasks/(.*)", h.VideoReformatResultHandler),
                (r"/video/flip/tasks", h.VideoReformatHandler),
                (r"/video/flip/ui", h.VideoReformatHandler),
                (r"/video/flip/ui/tasks/create", h.VideoReformatPostTaskUIHandler),
                (r"/video/flip/ui/tasks/(.*)/progress", h.VideoReformatTaskProgressSocket),
                (r"/video/flip/ui/tasks/(.*)", h.VideoReformatTaskHandler),
                (r"/video/flip/ui/tasks", h.VideoReformatTasksUIHandler),
            ]
        ### FALLBACK
        route_list.append((r"/.*", h.VideoReformatBaseHandler))
        self.add_handlers(r".*", route_list)

class TaskExecutor(PeriodicCallback):

    def __init__(self, task_queue, task_data):
        self.q = task_queue
        self.d = task_data
        super().__init__(self._do, 1e3)

    async def _do(self):
        while not self.q.empty():
            try:
                task = self.q.get()
                await task.run()
            finally:
                self.q.task_done()
