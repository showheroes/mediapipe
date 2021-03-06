from . import VideoReformatBaseHandler, VideoTaskBaseHandler
from ..util import VideoReformatTask

from bs4 import BeautifulSoup
import json
import math
import os
import shutil
import re
import uuid


class VideoReformatHandler(VideoReformatBaseHandler):
    """
    Creates a reformating request. Reads in the original video file from the
    request data or downloads it from the provided URL. Then places the video
    source file into the local filesystem, creates a task, queues the reformatting
    for processing and responds with a task ID.
    """

    def _get_accept_content_type(self):
        # to include files, form must be of type multipart/form-data
        return 'multipart/form-data'

    def _validate_request(self):
        # super()._validate_request()
        self.args = {}
        self.target_quality = self.get_argument('target_quality', 'high')
        self.action = self.get_argument('action', 'resize')
        self.target_size = self.get_argument('target_size', 'adjusted')
        self.target_format = self.get_argument('target_format', None)
        if 'flip' in self.action and not self.target_format:
            self._exit_error('No target format specified.', status=400)
        self.task_name = self.get_argument('taskname', '')
        if 'videofile' not in self.request.files:
            self._exit_error('No video file provided.', status=400)
        if not self.request.files['videofile']:
            self._exit_error('Video file not complete.', status=400)

    def _post_task(self):
        """ Creates a new task directory and places the submitted video there. """
        self._validate_request()
        # receive video file and put into filesystem
        # extract file and filename
        file_obj = self.request.files['videofile'][0]
        self.input_filename = file_obj['filename']

        # create a task ID, create the directory and place the file there
        task_id = str(uuid.uuid4())
        task_dir = self.get_task_dir(task_id)
        os.mkdir(task_dir)

        with open(os.path.join(task_dir, self.input_filename), 'wb') as input_file:
            input_file.write(file_obj['body'])
        if not self.task_name:
            self.task_name = 'task_' + task_id
        # save task_data
        task_data = {
            'task_name': self.task_name,
            'input_file_name': self.input_filename,
            'task_id': task_id,
            'action': self.action,
            'target_quality': self.target_quality,
            'target_size': self.target_size,
            'status': VideoReformatTask.STATUS_SUBMITTED
        }
        if 'flip' in self.action:
            task_data['target_format'] = self.target_format

        self.settings['tasks'][task_id] = task_data
        with open(os.path.join(task_dir, 'task_data'), 'w') as f:
            json.dump(task_data, f)

        # put task on queue
        self.settings['task_queue'].put(task_id)
        # return with task id
        return {
            'task_id': task_id,
            'task_name': self.task_name,
            'status': VideoReformatTask.STATUS_SUBMITTED
        }

    def get(self):
        """ Get a list of available tasks. """
        self._exit_success(list(self.settings['tasks'].keys()))

    def post(self):
        """ Creates a new task directory and places the submitted video there. """
        self._exit_success(self._post_task(), status=201)


class VideoReformatResultHandler(VideoTaskBaseHandler):
    """
    Provides information on the reformatting result, either by responding with an
    'in progress' or with a success message. In case of completeness, the result
    may be downloaded by adding a key only parameter 'download' to the call.
    """

    def get(self, task_id):
        """ Gets result information """
        # 1) find task in task list
        # 2) extract task status
        status = self.task_data['status']
        # 3) report either status or results if available (via download URL)
        if self.get_query_argument('download', None) is None:
            task_status = {'status': status, 'task_name': self.task_data['task_name']}
            if status == VideoReformatTask.STATUS_SUCCESS:
                dl_path = self.settings['deploy_path'] + '/tasks/' + task_id + '?download'
                task_status.update({'download_url': dl_path})
            self._exit_success(task_status)

        # 4) OR if get parameter download is set, respond with video file
        # (in case of success)
        if status == VideoReformatTask.STATUS_SUCCESS:
            self._send_file(self.task_data['output_file'], 'rb')
            self.set_status(200)
            self.finish()
            return
        self.set_status(204)
        self.finish()

    def delete(self, task_id):
        """ Deletes the given task. """
        success, msg = self.delete_task_dir(task_id)
        if not success:
            self._exit_error(msg, status=404)
        if msg:
            self._exit_warn({}, msg)
        # success and no message, all good
        self.set_status(204)
        self.finish()

    def delete_task_dir(self, task_id):
        if task_id not in self.settings['tasks']:
            return False, f'Task ID "{task_id}" unknown.'
        task_dir = self.get_task_dir(task_id)
        if not os.path.isdir(task_dir):
            return True, f'No data for task "{task_id}"'
        shutil.rmtree(task_dir)
        return True, ''


class VideoCaptionHandler(VideoTaskBaseHandler):
    """
    Responds with captions for the given task and language.
    Receives a Final Cut Pro XML description file and creates a WebVTT text
    track file from it.
    """

    def _validate_get(self):
        if 'captions' not in self.task_data:
            self._exit_error(f'No captions available for Video {self.task_id}', status=404)
        self.language = self.get_query_argument('language', None)
        if self.language is None:
            # no language provided, take first one
            self.language = list(self.task_data['captions'].keys())[0]

        # check for existence of language captions
        if self.language not in self.task_data['captions']:
            self._exit_error(f'No captions available for language {self.lang_dict[self.language]}', status=404)

    def _get_accept_content_type(self):
        # to include files, form must be of type multipart/form-data
        return 'multipart/form-data'

    def get(self, task_id):
        self._validate_get()
        captions_file = self.task_data['captions'][self.language]['file_path']
        self.set_header('Content-Type', 'text/vtt')
        self._send_file(captions_file)
        self.set_status(200)
        self.finish()

    def post(self, task_id):
        """ This receives the Final Cut XML file, extracts the captions and creates a WebVTT file from them."""
        self._convert_to_vtt()
        self.set_status(204)

    def _convert_to_vtt(self):
        self._validate_request()
        xml_file = self.request.files['fcpro_file'][0]

        # parse xml
        soup = BeautifulSoup(xml_file['body'], 'xml')
        # get the sequences
        sequences = soup.library.find_all('sequence')
        video_text_track = []
        for s in sequences:
            # find text and time codes
            duration = self._to_number(s['duration'])
            gap_offset = self._to_number(s.gap['offset'])  # offset against sequence
            gap_start = self._to_number(s.gap['start'])  # starting point of local timeline

            for title in s.gap.find_all('title'):
                t_start = self._to_number(title['offset']) - gap_start
                t_end = t_start + self._to_number(title['duration'])
                video_text_track.append(
                    f'{self._create_time_string(t_start)} --> {self._create_time_string(t_end)} region:1 align:middle\n')
                text_clean = re.sub(r'\n+', '\n', title.text).strip()
                video_text_track.append(f'{text_clean}\n\n')

        video_text_track_string = ''.join(video_text_track)
        if 'language' not in self.args or not self.args['language']:
            # detect subtitles language
            import langdetect
            langdetect.DetectorFactory.seed = 0
            self.args['language'] = langdetect.detect(video_text_track_string)

        captions_filename = f'{self.args["language"]}_subtitle.vtt'
        if 'captions' not in self.task_data:
            self.task_data['captions'] = {}
        self.task_data['captions'][self.args['language']] = {
            'file_path': os.path.join(self.settings['working_directory'],
                                      self.task_id, captions_filename),
            'captions_label': self.lang_dict[self.args['language']],
            'captions_source': f'api/tasks/{self.task_id}/captions?language={self.args["language"]}'
        }
        # update managed dict
        self.settings['tasks'][self.task_id] = self.task_data
        task_dir = os.path.join(self.settings['working_directory'], self.task_id)
        with open(os.path.join(task_dir, 'task_data'), 'w') as f:
            json.dump(self.task_data, f)

        with open(self.task_data['captions'][self.args['language']]['file_path'], 'w') as vtt_file:
            vtt_file.write(f'WEBVTT Kind: captions; Language: {self.args["language"]}\n\n')
            vtt_file.write('REGION\n')
            vtt_file.write('id:1\nwidth:40%\nlines:2\nregionanchor:0%,0%\nviewportanchor:30%,60%\nscroll:up\n\n')
            vtt_file.write(video_text_track_string)

    def _to_number(self, sec_string):
        sec_removed = sec_string.replace('s', '')
        if '/' in sec_removed:
            numerator, denominator = sec_removed.split('/')
            return math.floor(float(numerator) / float(denominator))
        return int(sec_removed)

    def _create_time_string(self, seconds):
        hrs = seconds // 3600
        hrs_rest_secs = seconds % 3600
        mins = hrs_rest_secs // 60
        min_rest_sec = hrs_rest_secs % 60
        return f'{hrs:02}:{mins:02}:{min_rest_sec:02}.000'
