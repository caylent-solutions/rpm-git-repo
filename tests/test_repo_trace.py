# Copyright 2022 The Android Open Source Project
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

"""Unittests for the repo_trace.py module."""

import os
import unittest
from unittest import mock

import pytest

import repo_trace


class TraceTests(unittest.TestCase):
    """Check Trace behavior."""

    def testTrace_MaxSizeEnforced(self):
        content = "git chicken"

        with repo_trace.Trace(content, first_trace=True):
            pass
        first_trace_size = os.path.getsize(repo_trace._TRACE_FILE)

        with repo_trace.Trace(content):
            pass
        self.assertGreater(
            os.path.getsize(repo_trace._TRACE_FILE), first_trace_size
        )

        # Check we clear everything is the last chunk is larger than _MAX_SIZE.
        with mock.patch("repo_trace._MAX_SIZE", 0):
            with repo_trace.Trace(content, first_trace=True):
                pass
            self.assertEqual(
                first_trace_size, os.path.getsize(repo_trace._TRACE_FILE)
            )

            # Check we only clear the chunks we need to.
            repo_trace._MAX_SIZE = (first_trace_size + 1) / (1024 * 1024)
            with repo_trace.Trace(content, first_trace=True):
                pass
            self.assertEqual(
                first_trace_size * 2, os.path.getsize(repo_trace._TRACE_FILE)
            )

            with repo_trace.Trace(content, first_trace=True):
                pass
            self.assertEqual(
                first_trace_size * 2, os.path.getsize(repo_trace._TRACE_FILE)
            )


@pytest.mark.unit
class TraceFileLocationTests(unittest.TestCase):
    """Tests for trace file location selection (fork feature)."""

    def test_fallback_to_tempdir_when_repo_dir_not_writable(self):
        """_GetTraceFile falls back to tempfile.gettempdir() when dir is not writable."""
        with mock.patch("os.access", return_value=False):
            with mock.patch(
                "tempfile.gettempdir", return_value="/tmp/fallback"
            ):
                result = repo_trace._GetTraceFile(quiet=True)
                self.assertIn("/tmp/fallback", result)

    def test_uses_repo_dir_when_writable(self):
        """_GetTraceFile uses repo directory when it is writable."""
        with mock.patch("os.access", return_value=True):
            result = repo_trace._GetTraceFile(quiet=True)
            # Should NOT contain tempdir fallback
            self.assertIn(repo_trace._TRACE_FILE_NAME, result)
