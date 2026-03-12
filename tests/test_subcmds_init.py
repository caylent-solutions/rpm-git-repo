# Copyright (C) 2020 The Android Open Source Project
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

"""Unittests for the subcmds/init.py module."""

import unittest
from unittest import mock

from subcmds import init


class InitCommand(unittest.TestCase):
    """Check registered all_commands."""

    def setUp(self):
        self.cmd = init.Init()

    def test_cli_parser_good(self):
        """Check valid command line options."""
        ARGV = ([],)
        for argv in ARGV:
            opts, args = self.cmd.OptionParser.parse_args(argv)
            self.cmd.ValidateOptions(opts, args)

    def test_cli_parser_bad(self):
        """Check invalid command line options."""
        ARGV = (
            # Too many arguments.
            ["url", "asdf"],
            # Conflicting options.
            ["--mirror", "--archive"],
        )
        for argv in ARGV:
            opts, args = self.cmd.OptionParser.parse_args(argv)
            with self.assertRaises(SystemExit):
                self.cmd.ValidateOptions(opts, args)


class InitExecuteRepoRevGuard(unittest.TestCase):
    """Check that check_repo_rev is skipped when .repo/repo is absent (pipx install)."""

    def _make_opt(
        self, repo_rev=None, repo_url=None, repo_verify=True, quiet=True
    ):
        opt = mock.MagicMock()
        opt.repo_rev = repo_rev
        opt.repo_url = repo_url
        opt.repo_verify = repo_verify
        opt.quiet = quiet
        opt.worktree = False
        opt.config_name = False
        return opt

    def _make_cmd_with_worktree(self, worktree_path):
        cmd = init.Init()
        cmd.manifest = mock.MagicMock()
        cmd.manifest.repoProject.worktree = worktree_path
        cmd.manifest.repoProject.GetRemote.return_value = mock.MagicMock()
        cmd.manifest.manifestProject.Exists = False
        cmd.git_event_log = mock.MagicMock()
        return cmd

    def test_check_repo_rev_skipped_when_worktree_absent(self):
        """check_repo_rev must not be called when .repo/repo does not exist."""
        cmd = self._make_cmd_with_worktree("/nonexistent/path/.repo/repo")
        opt = self._make_opt(repo_rev="feat/initial-rpm-git-repo")

        with (
            mock.patch("subcmds.init.Wrapper") as MockWrapper,
            mock.patch("subcmds.init.git_require", return_value=True),
            mock.patch("subcmds.init.WrapperDir", return_value="/fake/dir"),
            mock.patch.object(cmd, "_SyncManifest"),
            mock.patch.object(cmd, "_DisplayResult"),
            mock.patch("os.isatty", return_value=False),
            mock.patch("os.path.isdir", return_value=False),
        ):
            wrapper_instance = MockWrapper.return_value
            wrapper_instance.Requirements.from_dir.return_value = (
                mock.MagicMock(
                    get_hard_ver=mock.MagicMock(return_value=(2, 10, 0)),
                    get_soft_ver=mock.MagicMock(return_value=(2, 10, 0)),
                )
            )

            cmd.Execute(opt, [])

            wrapper_instance.check_repo_rev.assert_not_called()

    def test_check_repo_rev_called_when_worktree_present(self):
        """check_repo_rev must be called when .repo/repo exists as a git dir."""
        with mock.patch("os.path.isdir", return_value=True):
            cmd = self._make_cmd_with_worktree("/existing/.repo/repo")
            opt = self._make_opt(repo_rev="stable")

            with (
                mock.patch("subcmds.init.Wrapper") as MockWrapper,
                mock.patch("subcmds.init.git_require", return_value=True),
                mock.patch("subcmds.init.WrapperDir", return_value="/fake/dir"),
                mock.patch.object(cmd, "_SyncManifest"),
                mock.patch.object(cmd, "_DisplayResult"),
                mock.patch("os.isatty", return_value=False),
            ):
                wrapper_instance = MockWrapper.return_value
                wrapper_instance.Requirements.from_dir.return_value = (
                    mock.MagicMock(
                        get_hard_ver=mock.MagicMock(return_value=(2, 10, 0)),
                        get_soft_ver=mock.MagicMock(return_value=(2, 10, 0)),
                    )
                )
                wrapper_instance.check_repo_rev.return_value = (
                    "refs/heads/stable",
                    "abc123",
                )

                cmd.Execute(opt, [])

                wrapper_instance.check_repo_rev.assert_called_once_with(
                    "/existing/.repo/repo",
                    "stable",
                    repo_verify=opt.repo_verify,
                    quiet=opt.quiet,
                )

    def test_repo_rev_not_set_skips_check(self):
        """check_repo_rev must not be called when --repo-rev is not provided."""
        cmd = self._make_cmd_with_worktree("/existing/.repo/repo")
        opt = self._make_opt(repo_rev=None)

        with (
            mock.patch("subcmds.init.Wrapper") as MockWrapper,
            mock.patch("subcmds.init.git_require", return_value=True),
            mock.patch("subcmds.init.WrapperDir", return_value="/fake/dir"),
            mock.patch.object(cmd, "_SyncManifest"),
            mock.patch.object(cmd, "_DisplayResult"),
            mock.patch("os.isatty", return_value=False),
            mock.patch("os.path.isdir", return_value=True),
        ):
            wrapper_instance = MockWrapper.return_value
            wrapper_instance.Requirements.from_dir.return_value = (
                mock.MagicMock(
                    get_hard_ver=mock.MagicMock(return_value=(2, 10, 0)),
                    get_soft_ver=mock.MagicMock(return_value=(2, 10, 0)),
                )
            )

            cmd.Execute(opt, [])

            wrapper_instance.check_repo_rev.assert_not_called()
