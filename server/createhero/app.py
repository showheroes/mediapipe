import createhero.handler as h
from createhero.util import VideoReformatTask

from tornado.web import Application
from tornado.ioloop import PeriodicCallback
import logging
import os

class CreateHeroAPI(Application):

    def __init__(self, settings):
        super().__init__(**settings)
        self.log = logging.getLogger('CreateHeroAPI')
        self.add_routes()
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



class TaskExecutor(PeriodicCallback):

    def __init__(self, settings):
        self.q = settings['task_queue']
        self.d = settings['tasks']
        self.data_dir = settings['working_directory']
        self.log = logging.getLogger("TaskExecutor")
        super().__init__(self._do, 1e3)

    async def review_old_tasks(self):
        task_id_list = [f.name for f in os.scandir(self.data_dir) if f.is_dir()]
        for task_id in task_id_list:
            if task_id not in self.d:
                self.log.debug(f'loading task {task_id}')
                await self._load_or_create_and_run_task(task_id)

    async def _do(self):
        await self.review_old_tasks()
        while not self.q.empty():
            try:
                task_id = self.q.get()
                await self._load_or_create_and_run_task(task_id)
            finally:
                self.q.task_done()

    async def _load_or_create_and_run_task(self, task_id):
        task = VideoReformatTask(task_id, self.data_dir, self.d)
        if self.d[task_id]['status'] == VideoReformatTask.STATUS_INIT:
            await task.start()
