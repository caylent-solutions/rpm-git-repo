# Copyright 2019 The Android Open Source Project
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

"""Unittests for the ssh.py module."""

import multiprocessing
import subprocess
import unittest
from unittest import mock

import pytest

import ssh


class SshTests(unittest.TestCase):
    """Tests the ssh functions."""

    def test_parse_ssh_version(self):
        """Check _parse_ssh_version() handling."""
        ver = ssh._parse_ssh_version("Unknown\n")
        self.assertEqual(ver, ())
        ver = ssh._parse_ssh_version("OpenSSH_1.0\n")
        self.assertEqual(ver, (1, 0))
        ver = ssh._parse_ssh_version(
            "OpenSSH_6.6.1p1 Ubuntu-2ubuntu2.13, OpenSSL 1.0.1f 6 Jan 2014\n"
        )
        self.assertEqual(ver, (6, 6, 1))
        ver = ssh._parse_ssh_version(
            "OpenSSH_7.6p1 Ubuntu-4ubuntu0.3, OpenSSL 1.0.2n  7 Dec 2017\n"
        )
        self.assertEqual(ver, (7, 6))
        ver = ssh._parse_ssh_version("OpenSSH_9.0p1, LibreSSL 3.3.6\n")
        self.assertEqual(ver, (9, 0))

    def test_version(self):
        """Check version() handling."""
        with mock.patch("ssh._run_ssh_version", return_value="OpenSSH_1.2\n"):
            self.assertEqual(ssh.version(), (1, 2))

    def test_context_manager_empty(self):
        """Verify context manager with no clients works correctly."""
        with multiprocessing.Manager() as manager:
            with ssh.ProxyManager(manager):
                pass

    def test_context_manager_child_cleanup(self):
        """Verify orphaned clients & masters get cleaned up."""
        with multiprocessing.Manager() as manager:
            with ssh.ProxyManager(manager) as ssh_proxy:
                client = subprocess.Popen(["sleep", "964853320"])
                ssh_proxy.add_client(client)
                master = subprocess.Popen(["sleep", "964853321"])
                ssh_proxy.add_master(master)
        # If the process still exists, these will throw timeout errors.
        client.wait(0)
        master.wait(0)

    def test_ssh_sock(self):
        """Check sock() function."""
        manager = multiprocessing.Manager()
        proxy = ssh.ProxyManager(manager)
        with mock.patch("tempfile.mkdtemp", return_value="/tmp/foo"):
            # Old ssh version uses port.
            with mock.patch("ssh.version", return_value=(6, 6)):
                self.assertTrue(proxy.sock().endswith("%p"))

            proxy._sock_path = None
            # New ssh version uses hash.
            with mock.patch("ssh.version", return_value=(6, 7)):
                self.assertTrue(proxy.sock().endswith("%C"))


@pytest.mark.unit
class SshMandatoryTests(unittest.TestCase):
    """Tests for mandatory SSH behavior (fork feature)."""

    def test_ssh_not_installed_exits_with_error(self):
        """FileNotFoundError from ssh -V should cause sys.exit(1)."""
        ssh.version.cache_clear()
        with mock.patch(
            "ssh._run_ssh_version",
            side_effect=FileNotFoundError("ssh not found"),
        ):
            with mock.patch("sys.exit") as mock_exit:
                with mock.patch("builtins.print") as mock_print:
                    ssh.version()
                    mock_exit.assert_called_once_with(1)
                    mock_print.assert_called_once()
                    self.assertIn(
                        "fatal: ssh not installed",
                        mock_print.call_args[0][0],
                    )
        ssh.version.cache_clear()

    def test_ssh_called_process_error_exits(self):
        """CalledProcessError from ssh -V should cause sys.exit(1)."""
        ssh.version.cache_clear()
        with mock.patch(
            "ssh._run_ssh_version",
            side_effect=subprocess.CalledProcessError(
                1, "ssh", output=b"error"
            ),
        ):
            with mock.patch("sys.exit") as mock_exit:
                with mock.patch("builtins.print"):
                    ssh.version()
                    mock_exit.assert_called_once_with(1)
        ssh.version.cache_clear()

    def test_ssh_version_success_returns_tuple(self):
        """Normal ssh version parsing should return a tuple."""
        ssh.version.cache_clear()
        with mock.patch(
            "ssh._run_ssh_version",
            return_value="OpenSSH_8.9p1 Ubuntu-3, OpenSSL 3.0.2\n",
        ):
            result = ssh.version()
            self.assertEqual(result, (8, 9))
        ssh.version.cache_clear()
