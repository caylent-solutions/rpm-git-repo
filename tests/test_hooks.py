# Copyright (C) 2019 The Android Open Source Project
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

"""Unittests for the hooks.py module."""

import os
import unittest
import unittest.mock

import pytest

import hooks


class RepoHookShebang(unittest.TestCase):
    """Check shebang parsing in RepoHook."""

    def test_no_shebang(self):
        """Lines w/out shebangs should be rejected."""
        DATA = ("", "#\n# foo\n", "# Bad shebang in script\n#!/foo\n")
        for data in DATA:
            self.assertIsNone(hooks.RepoHook._ExtractInterpFromShebang(data))

    def test_direct_interp(self):
        """Lines whose shebang points directly to the interpreter."""
        DATA = (
            ("#!/foo", "/foo"),
            ("#! /foo", "/foo"),
            ("#!/bin/foo ", "/bin/foo"),
            ("#! /usr/foo ", "/usr/foo"),
            ("#! /usr/foo -args", "/usr/foo"),
        )
        for shebang, interp in DATA:
            self.assertEqual(
                hooks.RepoHook._ExtractInterpFromShebang(shebang), interp
            )

    def test_env_interp(self):
        """Lines whose shebang launches through `env`."""
        DATA = (
            ("#!/usr/bin/env foo", "foo"),
            ("#!/bin/env foo", "foo"),
            ("#! /bin/env /bin/foo ", "/bin/foo"),
        )
        for shebang, interp in DATA:
            self.assertEqual(
                hooks.RepoHook._ExtractInterpFromShebang(shebang), interp
            )


@pytest.mark.unit
class RepoHookInitTests(unittest.TestCase):
    """Tests for RepoHook initialization guard (fork feature)."""

    def test_script_fullpath_set_when_hooks_project_exists(self):
        """_script_fullpath is set when _hooks_project is provided."""
        mock_project = unittest.mock.MagicMock()
        mock_project.worktree = "/fake/worktree"
        hook = hooks.RepoHook(
            hook_type="pre-upload",
            hooks_project=mock_project,
            repo_topdir="/fake/topdir",
            manifest_url="https://example.com/manifest",
        )
        self.assertEqual(
            hook._script_fullpath,
            os.path.join("/fake/worktree", "pre-upload.py"),
        )

    def test_script_fullpath_none_when_no_hooks_project(self):
        """_script_fullpath is None when hooks_project is None."""
        hook = hooks.RepoHook(
            hook_type="pre-upload",
            hooks_project=None,
            repo_topdir="/fake/topdir",
            manifest_url="https://example.com/manifest",
        )
        self.assertIsNone(hook._script_fullpath)

    def test_run_noop_when_no_hooks_project(self):
        """Run should be a no-op (return True) when hooks_project is None."""
        hook = hooks.RepoHook(
            hook_type="pre-upload",
            hooks_project=None,
            repo_topdir="/fake/topdir",
            manifest_url="https://example.com/manifest",
        )
        result = hook.Run(project_list=[], worktree_list=[])
        self.assertTrue(result)

    def test_run_noop_when_bypass_hooks(self):
        """Run should be a no-op (return True) when bypass_hooks is True."""
        hook = hooks.RepoHook(
            hook_type="pre-upload",
            hooks_project=unittest.mock.MagicMock(),
            repo_topdir="/fake/topdir",
            manifest_url="https://example.com/manifest",
            bypass_hooks=True,
        )
        result = hook.Run(project_list=[], worktree_list=[])
        self.assertTrue(result)
