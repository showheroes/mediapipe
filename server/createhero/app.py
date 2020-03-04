import createhero.handler as h
from createhero.util import VideoReformatTask

from tornado.web import Application
from tornado.ioloop import PeriodicCallback
import logging

class CreateHeroAPI(Application):

    def __init__(self, settings):
        super().__init__(**settings)
        self.log = logging.getLogger('CreateHeroAPI')
        self.add_routes()
        self.read_old_tasks()
        self.log.info('CreateHero API ready')

    def add_routes(self):
        route_list = [
                (r"/video/flip/tasks/(.*)", h.VideoReformatResultHandler),
                (r"/video/flip/tasks", h.VideoReformatHandler),
                (r"/video/flip/ui", h.VideoReformatUIBaseHandler),
                (r"/video/flip/ui/tasks/create", h.VideoReformatPostTaskUIHandler),
                (r"/video/flip/ui/tasks/(.*)/progress", h.VideoReformatTaskProgressSocket),
                (r"/video/flip/ui/tasks/(.*)", h.VideoReformatTaskUIHandler),
                (r"/video/flip/ui/tasks", h.VideoReformatTasksUIHandler),
            ]
        ### FALLBACK
        # route_list.append((r"/.*", h.VideoReformatBaseHandler))
        self.add_handlers(r".*", route_list)

    def read_old_tasks(self):
        task_list = [f.name for f in os.scandir(self.settings['working_directory']) if f.is_dir()]
        for task in task_list:
            self.settings['tasks'][task] = {}
            VideoReformatTask(task, self.settings['working_directory'], self.settings['tasks'][task])


class TaskExecutor(PeriodicCallback):

    def __init__(self, settings):
        self.q = settings['task_queue']
        self.d = settings['tasks']
        self.data_dir = settings['working_directory']
        super().__init__(self._do, 1e3)

    async def _do(self):
        while not self.q.empty():
            try:
                task_id = self.q.get()
                task = VideoReformatTask(task_id, self.data_dir, self.d[task_id])
                await task.start()
            finally:
                self.q.task_done()
