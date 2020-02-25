import sys
import subprocess
import random
import time
import threading
import os
import Queue
import uuid

class AsynchronousFileReader(threading.Thread):
    '''
    Helper class to implement asynchronous reading of a file
    in a separate thread. Pushes read lines on a queue to
    be consumed in another thread.
    '''

    def __init__(self, fd, queue):
        assert isinstance(queue, Queue.Queue)
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

    STATUS_INIT = 'initialized'
    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_STOPPED = 'stopped'

    def __init__(self, working_base_dir, format, logging = False):
        self.logging = logging
        if self.logging:
            self.log_reader_queue = Queue.Queue()
        # save format
        self.format = format
        # create task id
        self.task_id = str(uuid.uuid4())
        self.status = self.STATUS_INIT
        self.progress = []

    def get_working_directory(self):
        return os.path.join(working_base_dir, self.task_id)

    def set_input_file(self, input_file):
        input_file_name, input_ext = os.path.splitext(input_file)
        output_file = input_file_name + '_' + format + input_ext
        self.input_file = os.path.join(self.get_working_directory(), input_file)
        self.output_file = os.path.join(self.get_working_directory(), output_file)

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
        if self.status != self.STATUS_INIT:
            return "Task not yet initialized."
        # Launch the command as subprocess, route stderr to stdout
        if self.logging:
            self.process = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            # Launch the asynchronous readers of the process' stdout and stderr.
            self.log_reader = AsynchronousFileReader(self.process.stdout, self.log_reader_queue)
            self.log_reader.start()
        else:
            self.process = subprocess.Popen(self.command)
        self.status = self.STATUS_RUNNING
        self.is_finished()

    def get_progress(self):
        if not self.logging:
            return ['']
        # get the progress from the subprocess
        while not self.log_reader_queue.empty():
            self.progress.append(self.log_reader_queue.get())
        return '\n'.join(progress)

    def is_finished(self):
        status = self.process.poll()
        if status:
            # Let's be tidy and join the threads we've started.
            log_reader.join()

            # Close subprocess' file descriptors.
            process.stdout.close()
            process.stderr.close()
            if status == 0:
                self.status = self.STATUS_SUCCESS
            else:
                self.status = self.STATUS_STOPPED
            return True
        return False
