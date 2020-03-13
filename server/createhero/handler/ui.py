from . import VideoReformatUIBaseHandler,VideoTaskUIBaseHandler
from .api import VideoReformatHandler, VideoCaptionHandler
from ..util import VideoReformatTask

import logging
from tornado.websocket import WebSocketHandler
import urllib.parse as up

class VideoReformatPostTaskUIHandler(VideoReformatHandler):
    """ Handler for creating reformating tasks. """

    def get(self):
        """ Render the input form. """
        self.render('post/post_task.html')

    def post(self):
        # validate the request and generate a uuid task_id, using the API method
        task = self._post_task(self)
        self.redirect(f'{self.settings["deploy_path"]}/video/flip/ui/tasks/{task["task_id"]}')

class VideoReformatTasksUIHandler(VideoReformatUIBaseHandler):

    def get(self):
        data = []
        for t in self.settings['tasks']:
            data.append(self.settings['tasks'][t])
        self.render('tasks/show_tasks.html', tasks=data)

class VideoReformatTaskUIHandler(VideoTaskUIBaseHandler):

    def get(self, task_id):
        if self.get_query_argument('download', None) != None and self.task_data['status'] == VideoReformatTask.STATUS_SUCCESS:
            self.set_header('Content-Type', 'video/mp4')
            self.set_header('Content-Disposition', f'attachment; filename={os.path.basename(self.task_data["output_file"])}')
            with open(self.task_data['output_file'], 'rb') as f:
                while 1:
                    data = f.read(16384) # or some other nice-sized chunk
                    if not data: break
                    self.write(data)
            self.finish()
        else:
            self.render('tasks/show_task.html', **task)

class VideoReformatTaskRestartHandler(VideoTaskUIBaseHandler):

    def get(self, task_id):
        self.task_data['progress'] = []
        self.task_data['status'] = VideoReformatTask.STATUS_SUBMITTED
        self.settings['tasks'][task_id] = self.task_data
        self.settings['task_queue'].put(task_id)
        self.render('tasks/show_task.html', **task)

class VideoReformatTaskProgressSocket(WebSocketHandler):
    """
    UI socket for monitoring a task, returns stdout messages and the download
    link when ready.
    """
    def check_origin(self, origin):
        parsed_origin = up.urlparse(origin)
        return '.showheroes.com' in parsed_origin.netloc

    def open(self, task_id):
        # when opening the websocket, get the task
        if not task_id in self.settings['tasks']:
            self.close(404, reason = f'No task with ID {task_id} found.')
        self.task_id =  task_id
        self.log = logging.getLogger("WebSocketHandler")

    def on_message(self, message):
        task = self.settings['tasks'][self.task_id]
        if 'progress' == message:
            answer = ''.join(list(map(lambda _in : _in.strip() + '<br/>', task['progress'])))
            self.write_message(answer)
        if task['status'] == VideoReformatTask.STATUS_STOPPED or task['status'] == VideoReformatTask.STATUS_SUCCESS:
            self.close(200, reason = "Process stopped")


class VideoAddCaptionHandler(VideoCaptionHandler):
    """ Render the input form for caption transformations and receive POST requests. """

    def get(self, task_id):
        self.render('captions/post_captions.html', **self.task_data)

    def post(self, task_id):
        self._convert_to_vtt()
        self.get(task_id)

class VideoCaptionPlayUIHandler(VideoCaptionHandler):
    """ Plays video with captions or creates new captions file. """

    def get(self, task_id):
        """ This renders the chosen video with the subtitles enabled. """
        self._validate_get()
        caption_data = self.task_data['captions'][self.language]['url']
        video_url = f'{self.settings["deploy_path"]}/static/video/{task_id}/{self.task_data["input_file_name"]}'
        self.render('captions/play_with_captions.html',
            video_url = video_url,
            captions_language = self.language,
            **caption_data)
