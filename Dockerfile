# Copyright 2019 The MediaPipe Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# FROM python:3.7-stretch
FROM nvidia/cuda:10.0-cudnn7-devel-ubuntu18.04

WORKDIR /mediapipe

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends gpg gpg-agent ca-certificates dirmngr && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        wget \
        unzip \
        # libopencv-core-dev \
        # libopencv-highgui-dev \
        # libopencv-imgproc-dev \
        # libopencv-video-dev \
        # libopencv-calib3d-dev \
        # libopencv-features2d-dev \
        software-properties-common

RUN add-apt-repository -y ppa:openjdk-r/ppa && \
        apt-get update -q
RUN apt-get install -y openjdk-8-jdk
RUN apt-get clean && \
        rm -rf /var/lib/apt/lists/*

RUN add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get install -y --no-install-recommends python3.7

# RUN apt update && apt install -y --no-install-recommends ffmpeg
RUN bash setup_opencv.sh

RUN pip install --upgrade setuptools
RUN pip install future
RUN pip install six

# Install bazel
ARG BAZEL_VERSION=1.1.0
RUN mkdir /bazel && \
    wget --no-check-certificate -O /bazel/installer.sh "https://github.com/bazelbuild/bazel/releases/download/${BAZEL_VERSION}/b\
azel-${BAZEL_VERSION}-installer-linux-x86_64.sh" && \
    wget --no-check-certificate -O  /bazel/LICENSE.txt "https://raw.githubusercontent.com/bazelbuild/bazel/master/LICENSE" && \
    chmod +x /bazel/installer.sh && \
    /bazel/installer.sh  && \
    rm -f /bazel/installer.sh

VOLUME /data

COPY ./mediapipe /mediapipe/mediapipe
COPY .bazelrc WORKSPACE BUILD /mediapipe/
COPY ./third_party /mediapipe/third_party

# RUN bazel build -c opt --define MEDIAPIPE_DISABLE_GPU=1 mediapipe/examples/desktop/autoflip:run_autoflip
RUN bazel build -c opt --copt -DMESA_EGL_NO_X11_HEADERS mediapipe/examples/desktop/autoflip:run_autoflip
# If we want the docker image to contain the pre-built object_detection_offline_demo binary, do the following
# RUN bazel build -c opt --define MEDIAPIPE_DISABLE_GPU=1 mediapipe/examples/desktop/demo:object_detection_tensorflow_demo

# setup the server
COPY ./server/requirements.txt /mediapipe/server/requirements.txt

WORKDIR /mediapipe/server

RUN pip install -r requirements.txt

COPY ./server/DataScienceHeroUtils /mediapipe/server/DataScienceHeroUtils

WORKDIR /mediapipe/server/DataScienceHeroUtils

RUN pip install -r requirements.txt && pip install .

COPY ./server /mediapipe/server

WORKDIR /mediapipe/server

CMD ["python", "service.py"]
