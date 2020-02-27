import sys
import subprocess
import random
import time
import threading
import os
import queue
import uuid

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
        self.working_base_dir = working_base_dir
        self.logging = logging
        if self.logging:
            self.log_reader_queue = queue.Queue()
        # save format
        self.format = task_data['target_format']
        # keep track of data
        self.task_data = task_data
        self.task_data['progress'] = []
        # create task id
        self.task_id = str(uuid.uuid4())
        os.mkdir(os.path.join(self.working_base_dir, self.task_id))
        self.task_data['status'] = self.STATUS_INIT
        # self.progress = []

    def get_task_directory(self):
        return os.path.join(self.working_base_dir, self.task_id)

    def set_input_file(self, input_file):
        input_file_name, input_ext = os.path.splitext(input_file)
        output_file = input_file_name + '_' + self.format + input_ext
        self.input_file = os.path.join(self.get_task_directory(), input_file)
        self.task_data['input_file'] = self.input_file
        self.output_file = os.path.join(self.get_task_directory(), output_file)
        self.task_data['output_file'] = self.output_file

        # prepare call to subprocess
        self.command = ['bazel-bin/mediapipe/examples/desktop/autoflip/run_autoflip',
                        '--calculator_graph_config_file=mediapipe/examples/desktop/autoflip/autoflip_graph.pbtxt',
                        f'--input_side_packets=input_video_path={self.input_file},output_video_path={self.output_file},aspect_ratio={self.format}'
                        ]

    def get_input_file(self):
        return self.input_file

    def get_output_file(self):
        return self.output_file

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
        self.task_data['status'] = self.STATUS_RUNNING
        if self.logging:
            while not self.is_finished() and not self.log_reader_queue.empty():
                self.task_data['progress'].append(self.log_reader_queue.get())

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
            # Let's be tidy and join the threads we've started.
            log_reader.join()

            # Close subprocess' file descriptors.
            process.stdout.close()
            process.stderr.close()
            if status == 0:
                self.task_data['status'] = self.STATUS_SUCCESS
            else:
                self.task_data['status'] = self.STATUS_STOPPED
            # put down the data into the directory for later inspection
            with open(os.path.join(self.get_task_directory(), 'process_output.txt')) as f:
                f.write('\n'.join(self.task_data['progress']))
            with open(os.path.join(self.get_task_directory(), 'STATE')) as f:
                f.write(self.status)
            return True
        return False
