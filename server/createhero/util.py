import sys
import subprocess
import random
import time
import threading
import os
import queue
import uuid
import json
import logging
class AsynchronousFileReader(threading.Thread):
    '''
    Helper class to implement asynchronous reading of a file
    in a separate thread. Pushes read lines on a queue to
    be consumed in another thread.
    '''

    def __init__(self, fd, queue):
        assert isinstance(queue, queue.Queue)
        assert callable(fd.readline)
        threading.Thread.__init__(self)
        self._fd = fd
        self._queue = queue

    def set_source(self, fd):
        assert callable(fd.readline)
        self._fd = fd

    def run(self):
        '''The body of the tread: read lines and put them on the queue.'''
        for line in iter(self._fd.readline, ''):
            self._queue.put(line)

    def eof(self):
        '''Check whether there is no more content to expect.'''
        return not self.is_alive() and self._queue.empty()


class VideoReformatTask(object):

    FORMAT_1x1 = '1:1'
    FORMAT_16x9 = '16:9'
    FORMAT_9x16 = '9:16'

    STATUS_SUBMITTED = 'submitted'
    STATUS_INIT = 'initialized'
    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_STOPPED = 'stopped'

    def __init__(self, task_id, working_base_dir, task_data, logging = False):
        self.log = logging.getLogger(__name__)
        self.task_id = task_id
        self.working_base_dir = working_base_dir
        self.task_data = task_data
        self.task_data['progress'] = []
        self.read_status()

        if self.task_data['status'] == self.STATUS_SUBMITTED:
            self.initialize()
            self.log_reader_queue = queue.Queue()
            self.prepare()
            self.set_status(self.STATUS_INIT)

    def get_task_directory(self):
        return os.path.join(self.working_base_dir, self.task_id)

    def read_status(self):
        self.log.debug('read task data')
        data_file = os.path.join(self.get_task_directory(), 'task_data')
        if os.path.isfile(data_file):
            self.log.debug('found json data, reading...')
            with open(data_file, 'r') as f:
                self.task_data.update(json.load(f))
        elif os.path.isdir(self.get_task_directory()) and [f.name for f in os.scandir(self.get_task_directory()) if f.is_file() and 'mp3' in f.name]:
            self.log.debug('no json data, but mp3 source file found')
            self.set_status(self.STATUS_STOPPED)
        else:
            self.log.debug('apparently a new task')
            self.set_status(self.STATUS_SUBMITTED)

    def set_status(self, status):
        self.task_data['status'] = status
        self.log.debug(f'setting task_data status to {status}, task_data now: {self.task_data}')
        with open(os.path.join(self.get_task_directory(), 'task_data'), 'w') as f:
            json.dump(self.task_data, f)

    def initialize(self):
        input_file_name, input_ext = os.path.splitext(self.task_data['input_file_name'])
        output_file_name = input_file_name + '_' + self.task_data['target_format'] + input_ext
        input_file = os.path.join(self.get_task_directory(), self.task_data['input_file_name'])
        self.task_data['input_file'] = input_file
        output_file = os.path.join(self.get_task_directory(), output_file_name)
        self.task_data['output_file'] = output_file

        audio_file = os.path.join(self.get_task_directory(), input_file_name + '.mp3')
        self.task_data['audio_file'] = audio_file
        input_no_audio = os.path.join(self.get_task_directory(), input_file_name + '_no_audio' + input_ext)
        self.task_data['input_file_no_audio'] = input_no_audio
        output_no_audio = os.path.join(self.get_task_directory(), input_file_name + '_' + self.task_data['target_format'] + '_no_audio' + input_ext)
        self.task_data['output_file_no_audio'] = output_no_audio

    def prepare(self):
        # extract audio from source
        extract_process = subprocess.run(['ffmpeg', '-i', input_file, '-f', 'mp3', '-b:a', '192k', '-vn', audio_file], capture_output=True, text=True)
        self.task_data['progress'].append(extract_process.stdout.splitlines())

        # strip audio off of input source
        stripoff_process = subprocess.run(['ffmpeg', '-i', input_file, '-c:v', 'copy', '-an', input_no_audio], capture_output=True, text=True)
        self.task_data['progress'].append(stripoff_process.stdout.splitlines())

        # prepare call to subprocess
        self.command = ['/mediapipe/bazel-bin/mediapipe/examples/desktop/autoflip/run_autoflip',
                        '--calculator_graph_config_file=/mediapipe/mediapipe/examples/desktop/autoflip/autoflip_graph.pbtxt',
                        f'--input_side_packets=input_video_path={input_no_audio},output_video_path={output_no_audio},aspect_ratio={self.task_data["target_format"]}'
                        ]

    async def start(self):
        if self.task_data['status'] != self.STATUS_INIT:
            return "Task not yet initialized."
        # Launch the command as subprocess, route stderr to stdout
        if self.logging:
            self.process = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            # Launch the asynchronous readers of the process' stdout and stderr.
            self.log_reader = AsynchronousFileReader(self.process.stdout, self.log_reader_queue)
            self.log_reader.run()
        else:
            self.process = subprocess.Popen(self.command)
            self.set_status(self.STATUS_RUNNING)
        while not self.is_finished():
            while not self.log_reader_queue.empty():
                self.task_data['progress'].append(self.log_reader_queue.get())
                self.set_status(self.STATUS_RUNNING)

    # def get_progress(self):
    #     if not self.logging:
    #         return ['']
    #     # get the progress from the subprocess
    #     while not self.log_reader_queue.empty():
    #         self.progress.append(self.log_reader_queue.get())
    #     return '\n'.join(progress)

    def is_finished(self):
        status = self.process.poll()
        if status:
            # rejoin video and audio
            join_process = subprocess.run(['ffmpeg', '-i', self.task_data['output_file_no_audio'], '-i', self.task_data['audio_file'], '-shortest', '-c:v', '-c:a', 'aac', '-b:a', '256k', self.task_data['output_file']], capture_output=True, text=True)
            self.task_data['progress'].append(join_process.stdout.splitlines())

            # Let's be tidy and join the threads we've started.
            log_reader.join()

            # Close subprocess' file descriptors.
            process.stdout.close()
            process.stderr.close()
            if status == 0:
                self.set_status(self.STATUS_SUCCESS)
            else:
                self.set_status(self.STATUS_STOPPED)
            return True
        return False
