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

"""Unittests for the project.py module."""

import contextlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import pytest

import error
import git_command
import git_config
import manifest_xml
import platform_utils
import project


@contextlib.contextmanager
def TempGitTree():
    """Create a new empty git checkout for testing."""
    with tempfile.TemporaryDirectory(prefix="repo-tests") as tempdir:
        # Tests need to assume, that main is default branch at init,
        # which is not supported in config until 2.28.
        cmd = ["git", "init"]
        if git_command.git_require((2, 28, 0)):
            cmd += ["--initial-branch=main"]
        else:
            # Use template dir for init.
            templatedir = tempfile.mkdtemp(prefix=".test-template")
            with open(os.path.join(templatedir, "HEAD"), "w") as fp:
                fp.write("ref: refs/heads/main\n")
            cmd += ["--template", templatedir]
        subprocess.check_call(cmd, cwd=tempdir)
        yield tempdir


class FakeProject:
    """A fake for Project for basic functionality."""

    def __init__(self, worktree):
        self.worktree = worktree
        self.gitdir = os.path.join(worktree, ".git")
        self.name = "fakeproject"
        self.work_git = project.Project._GitGetByExec(
            self, bare=False, gitdir=self.gitdir
        )
        self.bare_git = project.Project._GitGetByExec(
            self, bare=True, gitdir=self.gitdir
        )
        self.config = git_config.GitConfig.ForRepository(gitdir=self.gitdir)


class ReviewableBranchTests(unittest.TestCase):
    """Check ReviewableBranch behavior."""

    def test_smoke(self):
        """A quick run through everything."""
        with TempGitTree() as tempdir:
            fakeproj = FakeProject(tempdir)

            # Generate some commits.
            with open(os.path.join(tempdir, "readme"), "w") as fp:
                fp.write("txt")
            fakeproj.work_git.add("readme")
            fakeproj.work_git.commit("-mAdd file")
            fakeproj.work_git.checkout("-b", "work")
            fakeproj.work_git.rm("-f", "readme")
            fakeproj.work_git.commit("-mDel file")

            # Start off with the normal details.
            rb = project.ReviewableBranch(
                fakeproj, fakeproj.config.GetBranch("work"), "main"
            )
            self.assertEqual("work", rb.name)
            self.assertEqual(1, len(rb.commits))
            self.assertIn("Del file", rb.commits[0])
            d = rb.unabbrev_commits
            self.assertEqual(1, len(d))
            short, long = next(iter(d.items()))
            self.assertTrue(long.startswith(short))
            self.assertTrue(rb.base_exists)
            # Hard to assert anything useful about this.
            self.assertTrue(rb.date)

            # Now delete the tracking branch!
            fakeproj.work_git.branch("-D", "main")
            rb = project.ReviewableBranch(
                fakeproj, fakeproj.config.GetBranch("work"), "main"
            )
            self.assertEqual(0, len(rb.commits))
            self.assertFalse(rb.base_exists)
            # Hard to assert anything useful about this.
            self.assertTrue(rb.date)


class ProjectTests(unittest.TestCase):
    """Check Project behavior."""

    def test_encode_patchset_description(self):
        self.assertEqual(
            project.Project._encode_patchset_description("abcd00!! +"),
            "abcd00%21%21_%2b",
        )


class CopyLinkTestCase(unittest.TestCase):
    """TestCase for stub repo client checkouts.

    It'll have a layout like this:
      tempdir/          # self.tempdir
        checkout/       # self.topdir
          git-project/  # self.worktree

    Attributes:
      tempdir: A dedicated temporary directory.
      worktree: The top of the repo client checkout.
      topdir: The top of a project checkout.
    """

    def setUp(self):
        self.tempdirobj = tempfile.TemporaryDirectory(prefix="repo_tests")
        self.tempdir = self.tempdirobj.name
        self.topdir = os.path.join(self.tempdir, "checkout")
        self.worktree = os.path.join(self.topdir, "git-project")
        os.makedirs(self.topdir)
        os.makedirs(self.worktree)

    def tearDown(self):
        self.tempdirobj.cleanup()

    @staticmethod
    def touch(path):
        with open(path, "w"):
            pass

    def assertExists(self, path, msg=None):
        """Make sure |path| exists."""
        if os.path.exists(path):
            return

        if msg is None:
            msg = ["path is missing: %s" % path]
            while path != "/":
                path = os.path.dirname(path)
                if not path:
                    # If we're given something like "foo", abort once we get to
                    # "".
                    break
                result = os.path.exists(path)
                msg.append(f"\tos.path.exists({path}): {result}")
                if result:
                    msg.append("\tcontents: %r" % os.listdir(path))
                    break
            msg = "\n".join(msg)

        raise self.failureException(msg)


class CopyFile(CopyLinkTestCase):
    """Check _CopyFile handling."""

    def CopyFile(self, src, dest):
        return project._CopyFile(self.worktree, src, self.topdir, dest)

    def test_basic(self):
        """Basic test of copying a file from a project to the toplevel."""
        src = os.path.join(self.worktree, "foo.txt")
        self.touch(src)
        cf = self.CopyFile("foo.txt", "foo")
        cf._Copy()
        self.assertExists(os.path.join(self.topdir, "foo"))

    def test_src_subdir(self):
        """Copy a file from a subdir of a project."""
        src = os.path.join(self.worktree, "bar", "foo.txt")
        os.makedirs(os.path.dirname(src))
        self.touch(src)
        cf = self.CopyFile("bar/foo.txt", "new.txt")
        cf._Copy()
        self.assertExists(os.path.join(self.topdir, "new.txt"))

    def test_dest_subdir(self):
        """Copy a file to a subdir of a checkout."""
        src = os.path.join(self.worktree, "foo.txt")
        self.touch(src)
        cf = self.CopyFile("foo.txt", "sub/dir/new.txt")
        self.assertFalse(os.path.exists(os.path.join(self.topdir, "sub")))
        cf._Copy()
        self.assertExists(os.path.join(self.topdir, "sub", "dir", "new.txt"))

    def test_update(self):
        """Make sure changed files get copied again."""
        src = os.path.join(self.worktree, "foo.txt")
        dest = os.path.join(self.topdir, "bar")
        with open(src, "w") as f:
            f.write("1st")
        cf = self.CopyFile("foo.txt", "bar")
        cf._Copy()
        self.assertExists(dest)
        with open(dest) as f:
            self.assertEqual(f.read(), "1st")

        with open(src, "w") as f:
            f.write("2nd!")
        cf._Copy()
        with open(dest) as f:
            self.assertEqual(f.read(), "2nd!")

    def test_src_block_symlink(self):
        """Do not allow reading from a symlinked path."""
        src = os.path.join(self.worktree, "foo.txt")
        sym = os.path.join(self.worktree, "sym")
        self.touch(src)
        platform_utils.symlink("foo.txt", sym)
        self.assertExists(sym)
        cf = self.CopyFile("sym", "foo")
        self.assertRaises(error.ManifestInvalidPathError, cf._Copy)

    def test_src_block_symlink_traversal(self):
        """Do not allow reading through a symlink dir."""
        realfile = os.path.join(self.tempdir, "file.txt")
        self.touch(realfile)
        src = os.path.join(self.worktree, "bar", "file.txt")
        platform_utils.symlink(self.tempdir, os.path.join(self.worktree, "bar"))
        self.assertExists(src)
        cf = self.CopyFile("bar/file.txt", "foo")
        self.assertRaises(error.ManifestInvalidPathError, cf._Copy)

    def test_src_block_copy_from_dir(self):
        """Do not allow copying from a directory."""
        src = os.path.join(self.worktree, "dir")
        os.makedirs(src)
        cf = self.CopyFile("dir", "foo")
        self.assertRaises(error.ManifestInvalidPathError, cf._Copy)

    def test_dest_block_symlink(self):
        """Do not allow writing to a symlink."""
        src = os.path.join(self.worktree, "foo.txt")
        self.touch(src)
        platform_utils.symlink("dest", os.path.join(self.topdir, "sym"))
        cf = self.CopyFile("foo.txt", "sym")
        self.assertRaises(error.ManifestInvalidPathError, cf._Copy)

    def test_dest_block_symlink_traversal(self):
        """Do not allow writing through a symlink dir."""
        src = os.path.join(self.worktree, "foo.txt")
        self.touch(src)
        platform_utils.symlink(
            tempfile.gettempdir(), os.path.join(self.topdir, "sym")
        )
        cf = self.CopyFile("foo.txt", "sym/foo.txt")
        self.assertRaises(error.ManifestInvalidPathError, cf._Copy)

    def test_src_block_copy_to_dir(self):
        """Do not allow copying to a directory."""
        src = os.path.join(self.worktree, "foo.txt")
        self.touch(src)
        os.makedirs(os.path.join(self.topdir, "dir"))
        cf = self.CopyFile("foo.txt", "dir")
        self.assertRaises(error.ManifestInvalidPathError, cf._Copy)


class LinkFile(CopyLinkTestCase):
    """Check _LinkFile handling."""

    def LinkFile(self, src, dest):
        return project._LinkFile(self.worktree, src, self.topdir, dest)

    def test_basic(self):
        """Basic test of linking a file from a project into the toplevel."""
        src = os.path.join(self.worktree, "foo.txt")
        self.touch(src)
        lf = self.LinkFile("foo.txt", "foo")
        lf._Link()
        dest = os.path.join(self.topdir, "foo")
        self.assertExists(dest)
        self.assertTrue(os.path.islink(dest))
        self.assertEqual(
            os.path.join("git-project", "foo.txt"), os.readlink(dest)
        )

    def test_src_subdir(self):
        """Link to a file in a subdir of a project."""
        src = os.path.join(self.worktree, "bar", "foo.txt")
        os.makedirs(os.path.dirname(src))
        self.touch(src)
        lf = self.LinkFile("bar/foo.txt", "foo")
        lf._Link()
        self.assertExists(os.path.join(self.topdir, "foo"))

    def test_src_self(self):
        """Link to the project itself."""
        dest = os.path.join(self.topdir, "foo", "bar")
        lf = self.LinkFile(".", "foo/bar")
        lf._Link()
        self.assertExists(dest)
        self.assertEqual(os.path.join("..", "git-project"), os.readlink(dest))

    def test_dest_subdir(self):
        """Link a file to a subdir of a checkout."""
        src = os.path.join(self.worktree, "foo.txt")
        self.touch(src)
        lf = self.LinkFile("foo.txt", "sub/dir/foo/bar")
        self.assertFalse(os.path.exists(os.path.join(self.topdir, "sub")))
        lf._Link()
        self.assertExists(os.path.join(self.topdir, "sub", "dir", "foo", "bar"))

    def test_src_block_relative(self):
        """Do not allow relative symlinks."""
        BAD_SOURCES = (
            "./",
            "..",
            "../",
            "foo/.",
            "foo/./bar",
            "foo/..",
            "foo/../foo",
        )
        for src in BAD_SOURCES:
            lf = self.LinkFile(src, "foo")
            self.assertRaises(error.ManifestInvalidPathError, lf._Link)

    def test_update(self):
        """Make sure changed targets get updated."""
        dest = os.path.join(self.topdir, "sym")

        src = os.path.join(self.worktree, "foo.txt")
        self.touch(src)
        lf = self.LinkFile("foo.txt", "sym")
        lf._Link()
        self.assertEqual(
            os.path.join("git-project", "foo.txt"), os.readlink(dest)
        )

        # Point the symlink somewhere else.
        os.unlink(dest)
        platform_utils.symlink(self.tempdir, dest)
        lf._Link()
        self.assertEqual(
            os.path.join("git-project", "foo.txt"), os.readlink(dest)
        )


class LinkFileDirectoryTargetTests(CopyLinkTestCase):
    """Verification tests for <linkfile> with directory targets.

    Spec reference: Section 17.3 — Existing behaviors to preserve.

    The fork must not break linkfile with directory targets. When src
    is a directory, _Link() should create a symlink pointing to that
    directory relative to the dest location.
    """

    def LinkFile(self, src, dest):
        return project._LinkFile(self.worktree, src, self.topdir, dest)

    def test_spec_17_3_linkfile_directory_target_preserved(self):
        """Linkfile with directory src creates symlink to directory.

        Given: A project containing a subdirectory 'data/configs'.
        When: A linkfile links 'data/configs' to 'configs' under topdir.
        Then: A symlink is created at topdir/configs pointing to the
            directory, and the symlink target is valid.
        Spec: Section 17.3 — directory linkfile targets preserved.
        """
        # Create a directory with a file inside the project worktree.
        src_dir = os.path.join(self.worktree, "data", "configs")
        os.makedirs(src_dir)
        self.touch(os.path.join(src_dir, "settings.json"))

        lf = self.LinkFile("data/configs", "configs")
        lf._Link()

        dest = os.path.join(self.topdir, "configs")
        self.assertExists(dest)
        self.assertTrue(os.path.islink(dest))
        # The symlink target should be relative, pointing into git-project.
        link_target = os.readlink(dest)
        self.assertEqual(
            os.path.join("git-project", "data", "configs"), link_target
        )
        # The file inside the directory should be accessible through the link.
        linked_file = os.path.join(dest, "settings.json")
        self.assertTrue(
            os.path.exists(linked_file),
            f"File inside linked directory should be accessible: {linked_file}",
        )


class LinkFileAbsoluteDestTests(CopyLinkTestCase):
    """Tests for _LinkFile._Link() with absolute dest paths.

    Spec reference: Section 17.1 — Absolute Linkfile Dest.

    When dest is an absolute path, _Link() should:
    - Create parent directories at the absolute path
    - Create the symlink at the exact absolute path
    - Not use _SafeExpandPath for the dest

    When dest is relative, existing behavior is unchanged.
    """

    def LinkFile(self, src, dest):
        return project._LinkFile(self.worktree, src, self.topdir, dest)

    def test_spec_17_1_link_absolute_dest_creates_parents(self):
        """_Link() creates parent directories for absolute dest.

        Given: A _LinkFile with absolute dest in a non-existent dir tree.
        When: _Link() is called.
        Then: Parent directories are created.
        Spec: Section 17.1 — absolute dest creates parents.
        """
        src = os.path.join(self.worktree, "plugin.txt")
        self.touch(src)
        abs_dest = os.path.join(self.tempdir, "abs-out", "deep", "link")
        lf = self.LinkFile("plugin.txt", abs_dest)
        lf._Link()
        parent_dir = os.path.dirname(abs_dest)
        self.assertTrue(
            os.path.isdir(parent_dir),
            f"parent dir '{parent_dir}' should exist",
        )

    def test_spec_17_1_link_absolute_dest_creates_symlink(self):
        """_Link() creates symlink at the exact absolute dest path.

        Given: A _LinkFile with absolute dest.
        When: _Link() is called.
        Then: Symlink exists at the absolute dest path pointing to src.
        Spec: Section 17.1 — absolute dest creates symlink.
        """
        src = os.path.join(self.worktree, "plugin.txt")
        self.touch(src)
        abs_dest = os.path.join(self.tempdir, "abs-out", "link")
        lf = self.LinkFile("plugin.txt", abs_dest)
        lf._Link()
        self.assertTrue(
            os.path.islink(abs_dest),
            f"symlink should exist at '{abs_dest}'",
        )
        self.assertTrue(
            os.path.exists(abs_dest),
            f"symlink target should be resolvable at '{abs_dest}'",
        )

    def test_spec_17_1_link_relative_dest_uses_safe_expand(self):
        """_Link() uses _SafeExpandPath for relative dest (existing behavior).

        Given: A _LinkFile with relative dest.
        When: _Link() is called.
        Then: Symlink is created under topdir via _SafeExpandPath.
        Spec: Section 17.1 — relative dest backward compatibility.
        """
        src = os.path.join(self.worktree, "foo.txt")
        self.touch(src)
        lf = self.LinkFile("foo.txt", "relative-link")
        lf._Link()
        expected = os.path.join(self.topdir, "relative-link")
        self.assertExists(expected)
        self.assertTrue(
            os.path.islink(expected),
            f"relative dest should create symlink at '{expected}'",
        )

    def test_spec_17_1_link_absolute_dest_existing_parent_ok(self):
        """_Link() works when absolute dest parent directory already exists.

        Given: A _LinkFile with absolute dest in an existing directory.
        When: _Link() is called.
        Then: No error; symlink is created.
        Spec: Section 17.1 — existing parent dir no-error.
        """
        src = os.path.join(self.worktree, "plugin.txt")
        self.touch(src)
        abs_dir = os.path.join(self.tempdir, "existing-dir")
        os.makedirs(abs_dir)
        abs_dest = os.path.join(abs_dir, "link")
        lf = self.LinkFile("plugin.txt", abs_dest)
        lf._Link()
        self.assertTrue(
            os.path.islink(abs_dest),
            f"symlink should exist at '{abs_dest}'",
        )

    def test_spec_17_1_link_absolute_dest_rejects_path_traversal(self):
        """_Link() rejects absolute dest with '..' traversal components.

        Given: A _LinkFile with absolute dest containing '..'.
        When: _Link() is called.
        Then: ManifestInvalidPathError is raised.
        Spec: Section 17.1 — defense-in-depth path validation.
        """
        src = os.path.join(self.worktree, "plugin.txt")
        self.touch(src)
        abs_dest = os.path.join(self.tempdir, "abs-out", "..", "escape", "link")
        lf = self.LinkFile("plugin.txt", abs_dest)
        self.assertRaises(error.ManifestInvalidPathError, lf._Link)

    def test_spec_17_1_link_abs_dest_replaces_existing_symlink(self):
        """_Link() replaces an existing symlink at the absolute dest.

        Given: An existing symlink at the absolute dest path.
        When: _Link() is called with a different source.
        Then: The old symlink is replaced and points to the new source.
        Spec: Section 17.1 — existing symlink replacement.
        """
        src_old = os.path.join(self.worktree, "old.txt")
        src_new = os.path.join(self.worktree, "new.txt")
        self.touch(src_old)
        self.touch(src_new)
        abs_dest = os.path.join(self.tempdir, "abs-out", "link")
        # Create initial symlink via _Link with old source.
        lf_old = self.LinkFile("old.txt", abs_dest)
        lf_old._Link()
        self.assertTrue(os.path.islink(abs_dest))
        # Replace with new source.
        lf_new = self.LinkFile("new.txt", abs_dest)
        lf_new._Link()
        self.assertTrue(
            os.path.islink(abs_dest),
            f"symlink should still exist at '{abs_dest}'",
        )
        target = os.readlink(abs_dest)
        resolved = os.path.join(os.path.dirname(abs_dest), target)
        self.assertTrue(
            os.path.samefile(resolved, src_new),
            f"symlink should resolve to new source, got '{resolved}'",
        )

    def test_spec_17_1_link_abs_dest_deeply_nested_parents(self):
        """_Link() creates deeply nested parent directories for absolute dest.

        Given: An absolute dest with many levels of non-existent directories.
        When: _Link() is called.
        Then: All intermediate directories are created and symlink exists.
        Spec: Section 17.1 — deeply nested directory creation.
        """
        src = os.path.join(self.worktree, "deep.txt")
        self.touch(src)
        abs_dest = os.path.join(
            self.tempdir, "a", "b", "c", "d", "e", "f", "link"
        )
        lf = self.LinkFile("deep.txt", abs_dest)
        lf._Link()
        self.assertTrue(
            os.path.isdir(os.path.dirname(abs_dest)),
            "all intermediate parent directories should be created",
        )
        self.assertTrue(
            os.path.islink(abs_dest),
            f"symlink should exist at deeply nested path '{abs_dest}'",
        )

    def test_spec_17_1_link_abs_dest_trailing_slash(self):
        """_Link() handles absolute dest with trailing slash gracefully.

        Given: An absolute dest path ending with os.sep.
        When: _Link() is called.
        Then: The trailing slash is normalized and the symlink is created.
        Spec: Section 17.1 — trailing slash edge case.
        """
        src = os.path.join(self.worktree, "trail.txt")
        self.touch(src)
        # normpath strips trailing slash, so the link is created at the
        # normalized path.
        raw_dest = os.path.join(self.tempdir, "trail-out", "link") + os.sep
        normalized = os.path.normpath(raw_dest)
        lf = self.LinkFile("trail.txt", raw_dest)
        lf._Link()
        self.assertTrue(
            os.path.islink(normalized),
            f"symlink should exist at normalized path '{normalized}'",
        )


@pytest.mark.unit
class LinkFileExcludeTests(CopyLinkTestCase):
    """Tests for the exclude attribute on <linkfile>."""

    def LinkFile(self, src, dest, exclude=None):
        return project._LinkFile(
            self.worktree, src, self.topdir, dest, exclude=exclude
        )

    def _make_src_dir(self, name, children):
        """Create a source directory with the given children (files)."""
        src_dir = os.path.join(self.worktree, name)
        os.makedirs(src_dir, exist_ok=True)
        for child in children:
            child_path = os.path.join(src_dir, child)
            if os.path.basename(child) == child:
                self.touch(child_path)
            else:
                os.makedirs(os.path.dirname(child_path), exist_ok=True)
                self.touch(child_path)
        return src_dir

    def test_exclude_creates_real_directory(self):
        self._make_src_dir("pkg", ["a.py", "b.py"])
        dest = os.path.join(self.topdir, "linked-pkg")
        lf = self.LinkFile("pkg", dest, exclude="b.py")
        lf._Link()
        self.assertTrue(os.path.isdir(dest))
        self.assertFalse(os.path.islink(dest))

    def test_exclude_links_non_excluded_children(self):
        self._make_src_dir("pkg", ["a.py", "b.py", "c.py"])
        dest = os.path.join(self.topdir, "linked-pkg")
        lf = self.LinkFile("pkg", dest, exclude="b.py")
        lf._Link()
        self.assertTrue(os.path.islink(os.path.join(dest, "a.py")))
        self.assertTrue(os.path.islink(os.path.join(dest, "c.py")))

    def test_exclude_skips_excluded_children(self):
        self._make_src_dir("pkg", ["a.py", "tests"])
        dest = os.path.join(self.topdir, "linked-pkg")
        lf = self.LinkFile("pkg", dest, exclude="tests")
        lf._Link()
        self.assertFalse(os.path.exists(os.path.join(dest, "tests")))

    def test_exclude_multiple_comma_separated(self):
        self._make_src_dir("pkg", ["a.py", "tests", "docs", "__pycache__"])
        dest = os.path.join(self.topdir, "linked-pkg")
        lf = self.LinkFile("pkg", dest, exclude="tests,docs,__pycache__")
        lf._Link()
        self.assertTrue(os.path.islink(os.path.join(dest, "a.py")))
        self.assertFalse(os.path.exists(os.path.join(dest, "tests")))
        self.assertFalse(os.path.exists(os.path.join(dest, "docs")))
        self.assertFalse(os.path.exists(os.path.join(dest, "__pycache__")))

    def test_exclude_with_whitespace_in_csv(self):
        self._make_src_dir("pkg", ["a.py", "tests", "docs"])
        dest = os.path.join(self.topdir, "linked-pkg")
        lf = self.LinkFile("pkg", dest, exclude=" tests , docs ")
        lf._Link()
        self.assertTrue(os.path.islink(os.path.join(dest, "a.py")))
        self.assertFalse(os.path.exists(os.path.join(dest, "tests")))
        self.assertFalse(os.path.exists(os.path.join(dest, "docs")))

    def test_exclude_on_file_src_raises_error(self):
        src = os.path.join(self.worktree, "file.txt")
        self.touch(src)
        dest = os.path.join(self.topdir, "linked-file")
        lf = self.LinkFile("file.txt", dest, exclude="something")
        from error import ManifestInvalidPathError

        with self.assertRaises(ManifestInvalidPathError):
            lf._Link()

    def test_exclude_empty_string_behaves_as_no_exclude(self):
        self._make_src_dir("pkg", ["a.py", "b.py"])
        dest = os.path.join(self.topdir, "linked-pkg")
        lf = self.LinkFile("pkg", dest, exclude="")
        lf._Link()
        # Empty exclude -> single symlink to directory
        self.assertTrue(os.path.islink(dest))

    def test_exclude_with_absolute_dest(self):
        self._make_src_dir("pkg", ["a.py", "tests"])
        abs_dest = os.path.join(self.tempdir, "abs-out", "linked-pkg")
        lf = self.LinkFile("pkg", abs_dest, exclude="tests")
        lf._Link()
        self.assertTrue(os.path.isdir(abs_dest))
        self.assertFalse(os.path.islink(abs_dest))
        self.assertTrue(os.path.islink(os.path.join(abs_dest, "a.py")))
        self.assertFalse(os.path.exists(os.path.join(abs_dest, "tests")))

    def test_exclude_nonexistent_entry_no_error(self):
        self._make_src_dir("pkg", ["a.py"])
        dest = os.path.join(self.topdir, "linked-pkg")
        lf = self.LinkFile("pkg", dest, exclude="nonexistent")
        lf._Link()
        self.assertTrue(os.path.islink(os.path.join(dest, "a.py")))

    def test_no_exclude_preserves_directory_symlink(self):
        self._make_src_dir("pkg", ["a.py", "b.py"])
        dest = os.path.join(self.topdir, "linked-pkg")
        lf = self.LinkFile("pkg", dest)
        lf._Link()
        self.assertTrue(os.path.islink(dest))

    def test_exclude_with_glob_src_raises_error(self):
        self._make_src_dir("pkg", ["a.py"])
        dest = os.path.join(self.topdir, "linked-pkg")
        lf = self.LinkFile("pk*", dest, exclude="something")
        from error import ManifestInvalidPathError

        with self.assertRaises(ManifestInvalidPathError):
            lf._Link()

    def test_exclude_auto_skips_dot_git(self):
        src_dir = self._make_src_dir("pkg", ["a.py"])
        os.makedirs(os.path.join(src_dir, ".git"))
        dest = os.path.join(self.topdir, "linked-pkg")
        lf = self.LinkFile("pkg", dest, exclude="something")
        lf._Link()
        self.assertFalse(os.path.exists(os.path.join(dest, ".git")))
        self.assertTrue(os.path.islink(os.path.join(dest, "a.py")))

    def test_exclude_auto_skips_dot_repo(self):
        src_dir = self._make_src_dir("pkg", ["a.py"])
        os.makedirs(os.path.join(src_dir, ".repo"))
        os.makedirs(os.path.join(src_dir, ".repoconfig"))
        dest = os.path.join(self.topdir, "linked-pkg")
        lf = self.LinkFile("pkg", dest, exclude="something")
        lf._Link()
        self.assertFalse(os.path.exists(os.path.join(dest, ".repo")))
        self.assertFalse(os.path.exists(os.path.join(dest, ".repoconfig")))
        self.assertTrue(os.path.islink(os.path.join(dest, "a.py")))

    def test_exclude_auto_skips_dot_packages(self):
        src_dir = self._make_src_dir("pkg", ["a.py"])
        os.makedirs(os.path.join(src_dir, ".packages"))
        dest = os.path.join(self.topdir, "linked-pkg")
        lf = self.LinkFile("pkg", dest, exclude="something")
        lf._Link()
        self.assertFalse(os.path.exists(os.path.join(dest, ".packages")))
        self.assertTrue(os.path.islink(os.path.join(dest, "a.py")))

    def test_exclude_links_other_hidden_files(self):
        src_dir = self._make_src_dir("pkg", ["a.py"])
        self.touch(os.path.join(src_dir, ".config"))
        self.touch(os.path.join(src_dir, ".env"))
        dest = os.path.join(self.topdir, "linked-pkg")
        lf = self.LinkFile("pkg", dest, exclude="something")
        lf._Link()
        self.assertTrue(os.path.islink(os.path.join(dest, ".config")))
        self.assertTrue(os.path.islink(os.path.join(dest, ".env")))


_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture():
    """Load version constraint test data from fixture file."""
    fixture_path = os.path.join(_FIXTURES_DIR, "version_constraints_data.json")
    with open(fixture_path) as f:
        return json.load(f)


_VC_DATA = _load_fixture()
_GRI_DATA = _VC_DATA["get_revision_id"]


@pytest.mark.unit
class TestGetRevisionIdVersionConstraints:
    """Tests for version constraint integration in GetRevisionId().

    Spec reference: Section 17.2 — GetRevisionId integration.

    When revisionExpr contains a PEP 440 constraint, GetRevisionId()
    should detect it, resolve against available tags, and use the
    resolved tag for the normal checkout flow.
    """

    def test_spec_17_2_get_revision_id_detects_constraint(self):
        """GetRevisionId detects version constraint in revisionExpr.

        Given: A project with revisionExpr containing a PEP 440 constraint.
        When: GetRevisionId() is called.
        Then: is_version_constraint is invoked and detects the constraint.
        Spec: Section 17.2 — constraint detection triggers resolution.
        """
        import version_constraints
        from unittest.mock import MagicMock, patch

        proj = MagicMock(spec=project.Project)
        proj.revisionId = None
        proj.revisionExpr = _GRI_DATA["constraint_revision"]
        proj.name = "test-project"

        all_refs = {
            tag: f"commit_{i}" for i, tag in enumerate(_GRI_DATA["remote_tags"])
        }
        resolved_tag = _GRI_DATA["resolved_tag"]
        all_refs[resolved_tag] = _GRI_DATA["resolved_commit_id"]

        # Set up remote mock to convert resolved tag to local ref
        remote_mock = MagicMock()
        remote_mock.ToLocal.return_value = resolved_tag
        proj.GetRemote.return_value = remote_mock

        with patch.object(
            version_constraints,
            "is_version_constraint",
            return_value=True,
        ) as mock_detect:
            project.Project.GetRevisionId(proj, all_refs)
            mock_detect.assert_called_once_with(
                _GRI_DATA["constraint_revision"]
            )

    def test_spec_17_2_get_revision_id_resolves_to_tag(self):
        """GetRevisionId resolves constraint to highest matching tag.

        Given: A project with a version constraint revisionExpr.
        When: GetRevisionId() is called with all_refs containing tags.
        Then: The resolved tag's commit ID is returned via constraint
            resolution, not via the normal ToLocal path.
        Spec: Section 17.2 — resolved tag used for checkout.
        """
        import version_constraints
        from unittest.mock import MagicMock, patch

        proj = MagicMock(spec=project.Project)
        proj.revisionId = None
        proj.revisionExpr = _GRI_DATA["constraint_revision"]
        proj.name = "test-project"

        resolved_tag = _GRI_DATA["resolved_tag"]
        expected_commit = _GRI_DATA["resolved_commit_id"]

        # all_refs maps resolved tag to its commit, but does NOT
        # contain the constraint string itself — only the integration
        # code can resolve the constraint to the tag.
        all_refs = {
            tag: f"commit_{i}" for i, tag in enumerate(_GRI_DATA["remote_tags"])
        }
        all_refs[resolved_tag] = expected_commit

        # ToLocal would not know how to handle a constraint string,
        # so it should not be called for constraint revisions.
        remote_mock = MagicMock()
        remote_mock.ToLocal.side_effect = error.GitError(
            "ToLocal should not be called for constraint revisions"
        )
        proj.GetRemote.return_value = remote_mock

        with patch.object(
            version_constraints,
            "is_version_constraint",
            return_value=True,
        ):
            with patch.object(
                version_constraints,
                "resolve_version_constraint",
                return_value=resolved_tag,
            ):
                result = project.Project.GetRevisionId(proj, all_refs)
                assert result == expected_commit, (
                    f"expected commit '{expected_commit}', got '{result}'"
                )

    def test_spec_17_2_get_revision_id_non_constraint_passthrough(self):
        """Non-constraint revisionExpr passes through without resolution.

        Given: A project with revisionExpr "main" (not a constraint).
        When: GetRevisionId() is called.
        Then: resolve_version_constraint is never called.
        Spec: Section 17.2 — non-constraint passthrough.
        """
        import version_constraints
        from unittest.mock import MagicMock, patch

        proj = MagicMock(spec=project.Project)
        proj.revisionId = None
        proj.revisionExpr = _GRI_DATA["non_constraint_revision"]
        proj.name = "test-project"

        local_ref = "refs/remotes/origin/main"
        commit_id = "deadbeef12345678"
        all_refs = {local_ref: commit_id}

        remote_mock = MagicMock()
        remote_mock.ToLocal.return_value = local_ref
        proj.GetRemote.return_value = remote_mock

        with patch.object(
            version_constraints,
            "is_version_constraint",
            return_value=False,
        ) as mock_detect:
            with patch.object(
                version_constraints,
                "resolve_version_constraint",
            ) as mock_resolve:
                result = project.Project.GetRevisionId(proj, all_refs)
                mock_detect.assert_called_once_with(
                    _GRI_DATA["non_constraint_revision"]
                )
                mock_resolve.assert_not_called()
                assert result == commit_id

    def test_spec_17_2_get_revision_id_no_match_error(self):
        """No matching tags raises ManifestInvalidRevisionError.

        Given: A project with a constraint that matches no available tags.
        When: GetRevisionId() is called.
        Then: ManifestInvalidRevisionError is raised.
        Spec: Section 17.2 — error on no match.
        """
        import version_constraints
        from unittest.mock import MagicMock, patch

        proj = MagicMock(spec=project.Project)
        proj.revisionId = None
        proj.revisionExpr = _GRI_DATA["no_match_constraint"]
        proj.name = "test-project"

        all_refs = {
            tag: f"commit_{i}" for i, tag in enumerate(_GRI_DATA["remote_tags"])
        }

        with patch.object(
            version_constraints,
            "is_version_constraint",
            return_value=True,
        ):
            with patch.object(
                version_constraints,
                "resolve_version_constraint",
                side_effect=error.ManifestInvalidRevisionError(
                    "no tags match constraint"
                ),
            ):
                with pytest.raises(error.ManifestInvalidRevisionError):
                    project.Project.GetRevisionId(proj, all_refs)

    def test_spec_17_2_get_revision_id_collects_remote_tags(self):
        """GetRevisionId collects tags from all_refs for resolution.

        Given: A project with a constraint revisionExpr and all_refs
            containing tag entries.
        When: GetRevisionId() is called.
        Then: Tag names from all_refs are passed to
            resolve_version_constraint.
        Spec: Section 17.2 — tag collection from refs.
        """
        import version_constraints
        from unittest.mock import MagicMock, patch

        proj = MagicMock(spec=project.Project)
        proj.revisionId = None
        proj.revisionExpr = _GRI_DATA["constraint_revision"]
        proj.name = "test-project"

        resolved_tag = _GRI_DATA["resolved_tag"]
        expected_commit = _GRI_DATA["resolved_commit_id"]

        all_refs = {
            tag: f"commit_{i}" for i, tag in enumerate(_GRI_DATA["remote_tags"])
        }
        all_refs[resolved_tag] = expected_commit

        remote_mock = MagicMock()
        remote_mock.ToLocal.return_value = resolved_tag
        proj.GetRemote.return_value = remote_mock

        with patch.object(
            version_constraints,
            "is_version_constraint",
            return_value=True,
        ):
            with patch.object(
                version_constraints,
                "resolve_version_constraint",
                return_value=resolved_tag,
            ) as mock_resolve:
                project.Project.GetRevisionId(proj, all_refs)
                # Verify resolve was called with the revision and tag list
                mock_resolve.assert_called_once()
                call_args = mock_resolve.call_args
                assert call_args[0][0] == _GRI_DATA["constraint_revision"], (
                    "first arg should be the constraint revision"
                )
                passed_tags = call_args[0][1]
                for tag in _GRI_DATA["remote_tags"]:
                    assert tag in passed_tags, (
                        f"tag '{tag}' should be in the passed tag list"
                    )

    def test_spec_17_2_get_revision_id_no_refs_raises_error(self):
        """GetRevisionId raises error when all_refs is None for constraint.

        Given: A project with a constraint revisionExpr.
        When: GetRevisionId() is called with all_refs=None.
        Then: ManifestInvalidRevisionError is raised immediately.
        Spec: Section 17.2 — fail-fast on no refs available.
        """
        from unittest.mock import MagicMock

        proj = MagicMock(spec=project.Project)
        proj.revisionId = None
        proj.revisionExpr = _GRI_DATA["constraint_revision"]
        proj.name = "test-project"

        with pytest.raises(error.ManifestInvalidRevisionError):
            project.Project.GetRevisionId(proj, None)

    def test_spec_17_2_get_revision_id_wildcard_constraint(self):
        """GetRevisionId resolves wildcard constraint to latest tag.

        Given: A project with revisionExpr containing wildcard (*).
        When: GetRevisionId() is called with all_refs containing tags.
        Then: The latest tag's commit ID is returned.
        Spec: Section 17.2 — wildcard constraint with refs/tags/ prefix.
        """
        import version_constraints
        from unittest.mock import MagicMock, patch

        proj = MagicMock(spec=project.Project)
        proj.revisionId = None
        proj.revisionExpr = _GRI_DATA["wildcard_constraint_revision"]
        proj.name = "test-project"

        resolved_tag = _GRI_DATA["wildcard_resolved_tag"]
        expected_commit = _GRI_DATA["wildcard_resolved_commit_id"]

        all_refs = {
            tag: f"commit_{i}" for i, tag in enumerate(_GRI_DATA["remote_tags"])
        }
        all_refs[resolved_tag] = expected_commit

        with patch.object(
            version_constraints,
            "is_version_constraint",
            return_value=True,
        ):
            with patch.object(
                version_constraints,
                "resolve_version_constraint",
                return_value=resolved_tag,
            ):
                result = project.Project.GetRevisionId(proj, all_refs)
                assert result == expected_commit, (
                    f"wildcard should resolve to '{expected_commit}', "
                    f"got '{result}'"
                )


_INTEG_DATA = _VC_DATA["integration"]


class TestGetRevisionIdIntegration:
    """Integration tests for version constraint resolution through GetRevisionId.

    Spec reference: Section 5.5 and 17.2.

    These tests exercise the full pipeline: GetRevisionId() calls the real
    version_constraints module (no mocking of is_version_constraint or
    resolve_version_constraint) to detect and resolve PEP 440 constraints
    against mock tag sets. Each constraint type (compatible release, wildcard,
    range) is parameterized to verify correct resolution behavior.
    """

    @staticmethod
    def _build_all_refs(tags, expected_tag, expected_commit):
        """Build an all_refs dict mapping tags to commit IDs.

        Args:
            tags: List of tag ref strings.
            expected_tag: The tag that should resolve, mapped to expected_commit.
            expected_commit: The commit ID for the expected resolved tag.

        Returns:
            Dict mapping tag ref strings to commit ID strings.
        """
        all_refs = {tag: f"commit_{i}" for i, tag in enumerate(tags)}
        all_refs[expected_tag] = expected_commit
        return all_refs

    @pytest.mark.parametrize(
        "constraint_type",
        [
            pytest.param(
                "compatible_release",
                id="compatible_release_~=1.2.0_resolves_to_1.2.7",
            ),
            pytest.param(
                "wildcard",
                id="wildcard_*_resolves_to_latest",
            ),
            pytest.param(
                "range",
                id="range_>=1.0.0,<2.0.0_resolves_to_1.3.0",
            ),
        ],
    )
    def test_spec_5_5_integration_constraint_resolution(self, constraint_type):
        """Integration: PEP 440 constraint resolves to correct tag via GetRevisionId.

        Given: Mock tags from fixture data and a constraint revision.
        When: GetRevisionId() runs with real version_constraints module.
        Then: The correct tag's commit ID is returned.
        Spec: Section 5.5 — constraint types and resolution behavior.
        """
        from unittest.mock import MagicMock

        case = _INTEG_DATA[constraint_type]
        proj = MagicMock(spec=project.Project)
        proj.revisionId = None
        proj.revisionExpr = case["revision"]
        proj.name = "test-project"

        all_refs = self._build_all_refs(
            _INTEG_DATA["available_tags"],
            case["expected_tag"],
            case["expected_commit"],
        )

        result = project.Project.GetRevisionId(proj, all_refs)
        assert result == case["expected_commit"], (
            f"{constraint_type} constraint '{case['revision']}' should resolve to "
            f"'{case['expected_commit']}', got '{result}'"
        )


class MigrateWorkTreeTests(unittest.TestCase):
    """Check _MigrateOldWorkTreeGitDir handling."""

    _SYMLINKS = {
        "config",
        "description",
        "hooks",
        "info",
        "logs",
        "objects",
        "packed-refs",
        "refs",
        "rr-cache",
        "shallow",
        "svn",
    }
    _FILES = {
        "COMMIT_EDITMSG",
        "FETCH_HEAD",
        "HEAD",
        "index",
        "ORIG_HEAD",
        "unknown-file-should-be-migrated",
    }
    _CLEAN_FILES = {
        "a-vim-temp-file~",
        "#an-emacs-temp-file#",
    }

    @classmethod
    @contextlib.contextmanager
    def _simple_layout(cls):
        """Create a simple repo client checkout to test against."""
        with tempfile.TemporaryDirectory() as tempdir:
            tempdir = Path(tempdir)

            gitdir = tempdir / ".repo/projects/src/test.git"
            gitdir.mkdir(parents=True)
            cmd = ["git", "init", "--bare", str(gitdir)]
            subprocess.check_call(cmd)

            dotgit = tempdir / "src/test/.git"
            dotgit.mkdir(parents=True)
            for name in cls._SYMLINKS:
                (dotgit / name).symlink_to(
                    f"../../../.repo/projects/src/test.git/{name}"
                )
            for name in cls._FILES | cls._CLEAN_FILES:
                (dotgit / name).write_text(name)

            yield tempdir

    def test_standard(self):
        """Migrate a standard checkout that we expect."""
        with self._simple_layout() as tempdir:
            dotgit = tempdir / "src/test/.git"
            project.Project._MigrateOldWorkTreeGitDir(str(dotgit))

            # Make sure the dir was transformed into a symlink.
            self.assertTrue(dotgit.is_symlink())
            self.assertEqual(
                os.readlink(dotgit),
                os.path.normpath("../../.repo/projects/src/test.git"),
            )

            # Make sure files were moved over.
            gitdir = tempdir / ".repo/projects/src/test.git"
            for name in self._FILES:
                self.assertEqual(name, (gitdir / name).read_text())
            # Make sure files were removed.
            for name in self._CLEAN_FILES:
                self.assertFalse((gitdir / name).exists())

    def test_unknown(self):
        """A checkout with unknown files should abort."""
        with self._simple_layout() as tempdir:
            dotgit = tempdir / "src/test/.git"
            (tempdir / ".repo/projects/src/test.git/random-file").write_text(
                "one"
            )
            (dotgit / "random-file").write_text("two")
            with self.assertRaises(error.GitError):
                project.Project._MigrateOldWorkTreeGitDir(str(dotgit))

            # Make sure no content was actually changed.
            self.assertTrue(dotgit.is_dir())
            for name in self._FILES:
                self.assertTrue((dotgit / name).is_file())
            for name in self._CLEAN_FILES:
                self.assertTrue((dotgit / name).is_file())
            for name in self._SYMLINKS:
                self.assertTrue((dotgit / name).is_symlink())


class ManifestPropertiesFetchedCorrectly(unittest.TestCase):
    """Ensure properties are fetched properly."""

    def setUpManifest(self, tempdir):
        repodir = os.path.join(tempdir, ".repo")
        manifest_dir = os.path.join(repodir, "manifests")
        manifest_file = os.path.join(repodir, manifest_xml.MANIFEST_FILE_NAME)
        os.mkdir(repodir)
        os.mkdir(manifest_dir)
        manifest = manifest_xml.XmlManifest(repodir, manifest_file)

        return project.ManifestProject(
            manifest, "test/manifest", os.path.join(tempdir, ".git"), tempdir
        )

    def test_manifest_config_properties(self):
        """Test we are fetching the manifest config properties correctly."""

        with TempGitTree() as tempdir:
            fakeproj = self.setUpManifest(tempdir)

            # Set property using the expected Set method, then ensure
            # the porperty functions are using the correct Get methods.
            fakeproj.config.SetString(
                "manifest.standalone", "https://chicken/manifest.git"
            )
            self.assertEqual(
                fakeproj.standalone_manifest_url, "https://chicken/manifest.git"
            )

            fakeproj.config.SetString(
                "manifest.groups", "test-group, admin-group"
            )
            self.assertEqual(
                fakeproj.manifest_groups, "test-group, admin-group"
            )

            fakeproj.config.SetString("repo.reference", "mirror/ref")
            self.assertEqual(fakeproj.reference, "mirror/ref")

            fakeproj.config.SetBoolean("repo.dissociate", False)
            self.assertFalse(fakeproj.dissociate)

            fakeproj.config.SetBoolean("repo.archive", False)
            self.assertFalse(fakeproj.archive)

            fakeproj.config.SetBoolean("repo.mirror", False)
            self.assertFalse(fakeproj.mirror)

            fakeproj.config.SetBoolean("repo.worktree", False)
            self.assertFalse(fakeproj.use_worktree)

            fakeproj.config.SetBoolean("repo.clonebundle", False)
            self.assertFalse(fakeproj.clone_bundle)

            fakeproj.config.SetBoolean("repo.submodules", False)
            self.assertFalse(fakeproj.submodules)

            fakeproj.config.SetBoolean("repo.git-lfs", False)
            self.assertFalse(fakeproj.git_lfs)

            fakeproj.config.SetBoolean("repo.superproject", False)
            self.assertFalse(fakeproj.use_superproject)

            fakeproj.config.SetBoolean("repo.partialclone", False)
            self.assertFalse(fakeproj.partial_clone)

            fakeproj.config.SetString("repo.depth", "48")
            self.assertEqual(fakeproj.depth, 48)

            fakeproj.config.SetString("repo.depth", "invalid_depth")
            self.assertEqual(fakeproj.depth, None)

            fakeproj.config.SetString("repo.clonefilter", "blob:limit=10M")
            self.assertEqual(fakeproj.clone_filter, "blob:limit=10M")

            fakeproj.config.SetString(
                "repo.partialcloneexclude", "third_party/big_repo"
            )
            self.assertEqual(
                fakeproj.partial_clone_exclude, "third_party/big_repo"
            )

            fakeproj.config.SetString("manifest.platform", "auto")
            self.assertEqual(fakeproj.manifest_platform, "auto")


@pytest.mark.unit
class CopyFileLinkFileDataStructureTests(unittest.TestCase):
    """Tests for copyfile/linkfile data structure changes (fork feature).

    The fork changed _CopyFile and _LinkFile from NamedTuple to regular
    classes, and storage from dict to list.
    """

    def test_copyfile_is_mutable_class(self):
        """_CopyFile should be a regular class, not a NamedTuple."""
        cf = project._CopyFile("/worktree", "src.txt", "/topdir", "dest.txt")
        # Regular classes allow attribute modification; NamedTuples don't
        cf.src = "new_src.txt"
        self.assertEqual(cf.src, "new_src.txt")

    def test_linkfile_is_mutable_class(self):
        """_LinkFile should be a regular class, not a NamedTuple."""
        lf = project._LinkFile("/worktree", "src.txt", "/topdir", "dest.txt")
        lf.src = "new_src.txt"
        self.assertEqual(lf.src, "new_src.txt")
