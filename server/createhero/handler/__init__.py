from adhero_utils.handlers import GenericHandler

class VideoBaseHandler(GenericHandler):

    def prepare(self):
        super().prepare()
        # additional stuff here
        self.lang_dict = {
            'en' : 'English',
            'de' : 'Deutsch',
            'nl' : 'Nederlands',
            'fr' : 'Français'
        }

    def _authenticate(self):
        return

    def _send_file(self, filname, open_as = 'r'):
        with open(filname, open_as) as of:
            while 1:
                data = of.read(16384)
                if not data: break
                self.write(data)


class VideoUIMixin(VideoBaseHandler):

    def _get_response_content_type(self):
        return 'text/html'

    def render(self, template, **kwargs):
        super().render(template, deploy_path = self.settings['deploy_path'], **kwargs)

class VideoReformatBaseHandler(VideoBaseHandler):

    def get(self):
        # TODO: return documentation
        self._exit_success({})

class VideoReformatUIBaseHandler(VideoReformatBaseHandler, VideoUIMixin):
    """ UI base class, renders main page when called """

    def get(self):
        self.render('main.html')

class VideoTaskBaseHandler(VideoBaseHandler):

    def prepare(self):
        super().prepare()
        self.task_id = self.path_args[0]
        if not self.task_id in self.settings['tasks']:
            self._task_not_found()
        self.task_data = self.settings['tasks'][self.task_id]

    def _task_not_found(self):
        self._exit_error(f'Task with ID {self.task_id} not found.', status = 404)

class VideoTaskUIBaseHandler(VideoTaskBaseHandler, VideoUIMixin):

    def _task_not_found(self):
        self.render('tasks/show_task.html', task_id = self.task_id, status = None)

from . import api
from . import ui
