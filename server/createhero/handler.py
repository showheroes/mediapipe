from adhero_utils.handlers import GenericHandler
from .util import VideoReformatTask

import uuid
from tornado.websocket import WebSocketHandler
import os
import json
import urllib.parse as up
import logging

class VideoReformatBaseHandler(GenericHandler):

    def prepare(self):
        super().prepare()
        # additional stuff

    def get(self):
        # return documentation
        self._exit_success({})

    def _authenticate(self):
        return


class VideoReformatUIBaseHandler(GenericHandler):
    """ UI base class, renders main page when called """

    def prepare(self):
        super().prepare()
        # additional stuff here

    def _get_response_content_type(self):
        return 'text/html'

    def get(self):
        self.render('main.html')

    def _authenticate(self):
        return

    def render(self, template, **kwargs):
        super().render(template, deploy_path = self.settings['deploy_path'], **kwargs)

class VideoReformatPostTaskUIHandler(VideoReformatUIBaseHandler):

    def get(self):
        self.render('post/post_task.html')

    def _get_accept_content_type(self):
        return 'multipart/form-data'

    def _accept_content_type(self, content_type):
        self.log.info(f'got content type: {content_type}')
        return True

    def post(self):
        # validate the request and generate a uuid task_id
        VideoReformatHandler._validate_request(self)
        task = VideoReformatHandler._post_task(self)
        self.redirect(f'{self.settings["deploy_path"]}/video/flip/ui/tasks/{task["task_id"]}')

class VideoReformatTasksUIHandler(VideoReformatUIBaseHandler):

    def get(self):
        data = []
        for t in self.settings['tasks']:
            data.append({'task_id' : t, 'status' : self.settings['tasks'][t]['status']})
        self.render('tasks/show_tasks.html', tasks=data)

class VideoReformatTaskUIHandler(VideoReformatUIBaseHandler):

    def get(self, task_id):
        if not task_id in self.settings['tasks']:
            self.render('tasks/show_task.html', task_id = task_id, status = None)
        task = self.settings['tasks'][task_id]
        self.render('tasks/show_task.html', **task)

class VideoReformatTaskProgressSocket(WebSocketHandler):
    """
    UI socket for monitoring a task, returns stdout messages and the download link when ready.
    """
    def check_origin(self, origin):
        parsed_origin = up.urlparse(origin)
        let_through = '.showheroes.com' in parsed_origin.netloc
        return let_through

    def open(self, task_id):
        # when opening the websocket, get the task
        if not task_id in self.settings['tasks']:
            self.close(404, reason = f'No task with ID {task_id} found.')
        self.task = self.settings['tasks'][task_id]

    def on_message(self, message):
        if 'progress' == message:
            answer = ''.join(list(map(lambda _in : _in.strip() + '<br/>', self.task['progress'])))
            self.write_message(answer)
        if self.task['status'] == VideoReformatTask.STATUS_STOPPED or self.task['status'] == VideoReformatTask.STATUS_SUCCESS:
            self.close(200, reason = "Process stopped")




class VideoReformatHandler(VideoReformatBaseHandler):
    """
    Creates a reformating request. Reads in the original video file from the
    request data or downloads it from the provided URL. Then places the video
    source file into the local filesystem, creates a task, queues the reformatting
    for processing and responds with a task ID.
    """

    def _validate_request(self):
        self.log.info('validating request')
        self.args = {}
        tf = self.get_argument('target_format', None)
        if not tf:
            self._exit_error('No target format specified.', status = 400)
        self.target_format = tf
        if not 'videofile' in self.request.files:
            self._exit_error('No videofile provided.', status = 400)
        if not self.request.files['videofile']:
            self._exit_error('Videofile not complete.', status = 400)

    def _post_task(self):
        # receive video file and put into filesystem
        # extract file and filename
        file_obj = self.request.files['videofile'][0]
        self.input_filename = file_obj['filename']

        # create a task ID, create the directory and place the file there
        task_id = str(uuid.uuid4())
        task_dir = os.path.join(self.settings['working_directory'], task_id)
        os.mkdir(task_dir)

        with open(os.path.join(task_dir, self.input_filename), 'wb') as input_file:
            input_file.write(file_obj['body'])

        # save task_data
        task_data = {
            'target_format' : self.target_format,
            'input_file_name' : self.input_filename,
            'task_id' : task_id,
            'status' : VideoReformatTask.STATUS_SUBMITTED
        }
        self.settings['tasks'][task_id] = task_data
        with open(os.path.join(task_dir, 'task_data'), 'w') as f:
            json.dump(task_data, f)

        # put task on queue
        self.settings['task_queue'].put(task_id)
        # return with task id
        return {'task_id' : task_id, 'status' : VideoReformatTask.STATUS_SUBMITTED}

    def get(self):
        self._exit_success(list(self.settings['tasks'].keys()))

    def post(self):
        self._validate_request()
        self._exit_success(self._post_task())


class VideoReformatResultHandler(VideoReformatBaseHandler):
    """
    Provides information on the reformatting result, either by responding with an
    'in progress' or with a success message. In case of completeness, the result
    may be downloaded by adding a key only parameter 'download' to the call.
    """

    def get(self, task_id):
        # 1) find task in task list
        if not task_id in self.settings['tasks']:
            self._exit_error(f'Task with ID {task_id} not found.', status = 404)
        task = self.settings['tasks'][task_id]
        # 2) extract task status
        status = task['status']
        # 3) report either status or results if available (via download URL)
        if not self.get_query_argument('download', None):
            task_status = {'status' : status}
            if status == VideoReformatTask.STATUS_SUCCESS:
                task_status.update({'download_url' : 'some_url?download'})
            self._exit_success(task_status)

        # 4) OR if get parameter download is set, respond with video file
        if status == VideoReformatTask.STATUS_SUCCESS:
            with open(task['output_file'], 'rb') as of:
                while 1:
                    data = of.read(16384)
                    if not data: break
                    self.write(data)
            self.set_status(200)
            self.finish()
        self.set_status(204)
        self.finish()
