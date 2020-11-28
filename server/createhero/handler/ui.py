import json

from . import VideoReformatUIBaseHandler, VideoTaskUIBaseHandler, VideoUIMixin
from .api import VideoReformatHandler, VideoCaptionHandler, VideoReformatResultHandler
from ..util import VideoReformatTask

import logging
import os
from tornado.websocket import WebSocketHandler
import urllib.parse as up


class VideoReformatPostTaskUIHandler(VideoReformatHandler, VideoUIMixin):
    """ Handler for creating reformating tasks. """

    def get(self):
        """ Render the input form. """
        self.render('post/post_task.html')

    def post(self):
        # validate the request and generate a uuid task_id, using the API method
        task = self._post_task()
        self.redirect(f'{self.settings["deploy_path"]}/tasks/{task["task_id"]}')


class VideoReformatTasksUIHandler(VideoReformatUIBaseHandler):

    def get(self):
        self.render('tasks/show_tasks.html', tasks=list(self.settings['tasks'].values()))


class VideoReformatTaskUIHandler(VideoTaskUIBaseHandler):

    def get(self, task_id):
        if self.get_query_argument('download', None) is not None \
                and self.task_data['status'] == VideoReformatTask.STATUS_SUCCESS:
            self.set_header('Content-Type', 'video/mp4')
            self.set_header('Content-Disposition',
                            f'attachment; filename={os.path.basename(self.task_data["output_file"])}')
            self._send_file(self.task_data['output_file'], 'rb')
            self.finish()
        else:
            self.render('tasks/show_task.html', **self.task_data)


class VideoReformatTaskDeleteHandler(VideoReformatResultHandler, VideoUIMixin):

    def get(self, task_id):
        success, msg = self.delete_task_dir(task_id)
        del self.settings['tasks'][task_id]
        messages = []
        if not success:
            messages.append({'type': 'danger', 'message': msg})
        elif msg:
            messages.append({'type': 'warning', 'message': msg})
        else:
            messages.append({'type': 'success', 'message': f'Deleted data for task ID {task_id}'})
        self.render('tasks/show_tasks.html', tasks=list(self.settings['tasks'].values()), messages=messages)


class VideoReformatTaskRestartHandler(VideoTaskUIBaseHandler):

    def get(self, task_id):
        self.task_data['progress'] = []
        self.task_data['status'] = VideoReformatTask.STATUS_SUBMITTED
        self.settings['tasks'][task_id] = self.task_data
        self.settings['task_queue'].put(task_id)
        self.render('tasks/show_task.html', **self.task_data)


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
        if task_id not in self.settings['tasks']:
            self.close(404, reason=f'No task with ID {task_id} found.')
        self.task_id = task_id
        self.log = logging.getLogger("WebSocketHandler")

    def on_message(self, message):
        task = self.settings['tasks'][self.task_id]
        mo = json.loads(message)
        answer = {}
        if 'progress' in mo['command']:
            answer['data'] = ''.join(list(map(lambda _in: _in.strip() + '<br/>', task['progress'])))
        if task['status'] == VideoReformatTask.STATUS_STOPPED or task['status'] == VideoReformatTask.STATUS_SUCCESS:
            answer['type'] = 'complete'
        else:
            answer['type'] = 'progress'
        self.write_message(json.dumps(answer))
        
    def on_close(self) -> None:
        self.log.info("websocket has been closed")


class VideoAddCaptionHandler(VideoCaptionHandler, VideoUIMixin):
    """ Render the input form for caption transformations and receive POST requests. """

    def _validate_request(self):
        self.args = {}
        lang = self.get_argument('language', None)
        if lang != None:
            self.args['language'] = lang

    def get(self, task_id):
        self.render('captions/post_captions.html', **self.task_data)

    def post(self, task_id):
        self._convert_to_vtt()
        self.get(task_id)


class VideoCaptionPlayUIHandler(VideoCaptionHandler, VideoUIMixin):
    """ Plays video with captions or creates new captions file. """

    def get(self, task_id):
        """ This renders the chosen video with the subtitles enabled. """
        self._validate_get()
        caption_data = self.task_data['captions'][self.language]
        video_url = f'{self.settings["deploy_path"]}/static/video/{task_id}/{self.task_data["input_file_name"]}'
        self.render('captions/play_with_captions.html', video_url=video_url, captions_language=self.language,
                    **caption_data)

    def post(self, task_id):
        self._exit_no_route('POST')
