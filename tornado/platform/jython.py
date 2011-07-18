#!/usr/bin/env python
#
# Copyright 2011 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Jython implementations of platform-specific functionality."""

from java.nio import ByteBuffer
from java.nio.channels import Pipe
from org.python.core.util import StringUtil

from tornado.platform import interface

def set_close_exec(fd):
    pass

class Waker(interface.Waker):
    def __init__(self):
        pipe = Pipe.open()
        self.reader = pipe.source()
        self.writer = pipe.sink()
        self.reader.configureBlocking(False)
        self.writer.configureBlocking(False)

    def fileno(self):
        return self

    def getchannel(self):
        return self.reader

    def wake(self):
        self.writer.write(ByteBuffer.wrap(StringUtil.toBytes("x")))

    def consume(self):
        while True:
            buffer = ByteBuffer.allocate(4096)
            num_bytes = self.reader.read(buffer)
            if num_bytes <= 0:
                break

    def close(self):
        self.reader.close()
        self.writer.close()
