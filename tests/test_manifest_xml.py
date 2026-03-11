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

"""Unittests for the manifest_xml.py module."""

import os
import platform
import re
import tempfile
import unittest
import xml.dom.minidom

import error
import manifest_xml
import project


# Invalid paths that we don't want in the filesystem.
INVALID_FS_PATHS = (
    "",
    ".",
    "..",
    "../",
    "./",
    ".//",
    "foo/",
    "./foo",
    "../foo",
    "foo/./bar",
    "foo/../../bar",
    "/foo",
    "./../foo",
    ".git/foo",
    # Check case folding.
    ".GIT/foo",
    "blah/.git/foo",
    ".repo/foo",
    ".repoconfig",
    # Block ~ due to 8.3 filenames on Windows filesystems.
    "~",
    "foo~",
    "blah/foo~",
    # Block Unicode characters that get normalized out by filesystems.
    "foo\u200cbar",
    # Block newlines.
    "f\n/bar",
    "f\r/bar",
)

# Make sure platforms that use path separators (e.g. Windows) are also
# rejected properly.
if os.path.sep != "/":
    INVALID_FS_PATHS += tuple(
        x.replace("/", os.path.sep) for x in INVALID_FS_PATHS
    )


def sort_attributes(manifest):
    """Sort the attributes of all elements alphabetically.

    This is needed because different versions of the toxml() function from
    xml.dom.minidom outputs the attributes of elements in different orders.
    Before Python 3.8 they were output alphabetically, later versions preserve
    the order specified by the user.

    Args:
        manifest: String containing an XML manifest.

    Returns:
        The XML manifest with the attributes of all elements sorted
        alphabetically.
    """
    new_manifest = ""
    # This will find every element in the XML manifest, whether they have
    # attributes or not. This simplifies recreating the manifest below.
    matches = re.findall(
        r'(<[/?]?[a-z-]+\s*)((?:\S+?="[^"]+"\s*?)*)(\s*[/?]?>)', manifest
    )
    for head, attrs, tail in matches:
        m = re.findall(r'\S+?="[^"]+"', attrs)
        new_manifest += head + " ".join(sorted(m)) + tail
    return new_manifest


class ManifestParseTestCase(unittest.TestCase):
    """TestCase for parsing manifests."""

    def setUp(self):
        self.tempdirobj = tempfile.TemporaryDirectory(prefix="repo_tests")
        self.tempdir = self.tempdirobj.name
        self.repodir = os.path.join(self.tempdir, ".repo")
        self.manifest_dir = os.path.join(self.repodir, "manifests")
        self.manifest_file = os.path.join(
            self.repodir, manifest_xml.MANIFEST_FILE_NAME
        )
        self.local_manifest_dir = os.path.join(
            self.repodir, manifest_xml.LOCAL_MANIFESTS_DIR_NAME
        )
        os.mkdir(self.repodir)
        os.mkdir(self.manifest_dir)

        # The manifest parsing really wants a git repo currently.
        gitdir = os.path.join(self.repodir, "manifests.git")
        os.mkdir(gitdir)
        with open(os.path.join(gitdir, "config"), "w") as fp:
            fp.write(
                """[remote "origin"]
        url = https://localhost:0/manifest
"""
            )

    def tearDown(self):
        self.tempdirobj.cleanup()

    def getXmlManifest(self, data):
        """Helper to initialize a manifest for testing."""
        with open(self.manifest_file, "w", encoding="utf-8") as fp:
            fp.write(data)
        return manifest_xml.XmlManifest(self.repodir, self.manifest_file)

    @staticmethod
    def encodeXmlAttr(attr):
        """Encode |attr| using XML escape rules."""
        return attr.replace("\r", "&#x000d;").replace("\n", "&#x000a;")


class ManifestValidateFilePaths(unittest.TestCase):
    """Check _ValidateFilePaths helper.

    This doesn't access a real filesystem.
    """

    def check_both(self, *args):
        manifest_xml.XmlManifest._ValidateFilePaths("copyfile", *args)
        manifest_xml.XmlManifest._ValidateFilePaths("linkfile", *args)

    def test_normal_path(self):
        """Make sure good paths are accepted."""
        self.check_both("foo", "bar")
        self.check_both("foo/bar", "bar")
        self.check_both("foo", "bar/bar")
        self.check_both("foo/bar", "bar/bar")

    def test_symlink_targets(self):
        """Some extra checks for symlinks."""

        def check(*args):
            manifest_xml.XmlManifest._ValidateFilePaths("linkfile", *args)

        # We allow symlinks to end in a slash since we allow them to point to
        # dirs in general.  Technically the slash isn't necessary.
        check("foo/", "bar")
        # We allow a single '.' to get a reference to the project itself.
        check(".", "bar")

    def test_bad_paths(self):
        """Make sure bad paths (src & dest) are rejected."""
        for path in INVALID_FS_PATHS:
            self.assertRaises(
                error.ManifestInvalidPathError, self.check_both, path, "a"
            )
            self.assertRaises(
                error.ManifestInvalidPathError, self.check_both, "a", path
            )


class ValueTests(unittest.TestCase):
    """Check utility parsing code."""

    def _get_node(self, text):
        return xml.dom.minidom.parseString(text).firstChild

    def test_bool_default(self):
        """Check XmlBool default handling."""
        node = self._get_node("<node/>")
        self.assertIsNone(manifest_xml.XmlBool(node, "a"))
        self.assertIsNone(manifest_xml.XmlBool(node, "a", None))
        self.assertEqual(123, manifest_xml.XmlBool(node, "a", 123))

        node = self._get_node('<node a=""/>')
        self.assertIsNone(manifest_xml.XmlBool(node, "a"))

    def test_bool_invalid(self):
        """Check XmlBool invalid handling."""
        node = self._get_node('<node a="moo"/>')
        self.assertEqual(123, manifest_xml.XmlBool(node, "a", 123))

    def test_bool_true(self):
        """Check XmlBool true values."""
        for value in ("yes", "true", "1"):
            node = self._get_node(f'<node a="{value}"/>')
            self.assertTrue(manifest_xml.XmlBool(node, "a"))

    def test_bool_false(self):
        """Check XmlBool false values."""
        for value in ("no", "false", "0"):
            node = self._get_node(f'<node a="{value}"/>')
            self.assertFalse(manifest_xml.XmlBool(node, "a"))

    def test_int_default(self):
        """Check XmlInt default handling."""
        node = self._get_node("<node/>")
        self.assertIsNone(manifest_xml.XmlInt(node, "a"))
        self.assertIsNone(manifest_xml.XmlInt(node, "a", None))
        self.assertEqual(123, manifest_xml.XmlInt(node, "a", 123))

        node = self._get_node('<node a=""/>')
        self.assertIsNone(manifest_xml.XmlInt(node, "a"))

    def test_int_good(self):
        """Check XmlInt numeric handling."""
        for value in (-1, 0, 1, 50000):
            node = self._get_node(f'<node a="{value}"/>')
            self.assertEqual(value, manifest_xml.XmlInt(node, "a"))

    def test_int_invalid(self):
        """Check XmlInt invalid handling."""
        with self.assertRaises(error.ManifestParseError):
            node = self._get_node('<node a="xx"/>')
            manifest_xml.XmlInt(node, "a")


class XmlManifestTests(ManifestParseTestCase):
    """Check manifest processing."""

    def test_empty(self):
        """Parse an 'empty' manifest file."""
        manifest = self.getXmlManifest(
            '<?xml version="1.0" encoding="UTF-8"?><manifest></manifest>'
        )
        self.assertEqual(manifest.remotes, {})
        self.assertEqual(manifest.projects, [])

    def test_link(self):
        """Verify Link handling with new names."""
        manifest = manifest_xml.XmlManifest(self.repodir, self.manifest_file)
        with open(os.path.join(self.manifest_dir, "foo.xml"), "w") as fp:
            fp.write("<manifest></manifest>")
        manifest.Link("foo.xml")
        with open(self.manifest_file) as fp:
            self.assertIn('<include name="foo.xml" />', fp.read())

    def test_toxml_empty(self):
        """Verify the ToXml() helper."""
        manifest = self.getXmlManifest(
            '<?xml version="1.0" encoding="UTF-8"?><manifest></manifest>'
        )
        self.assertEqual(
            manifest.ToXml().toxml(), '<?xml version="1.0" ?><manifest/>'
        )

    def test_todict_empty(self):
        """Verify the ToDict() helper."""
        manifest = self.getXmlManifest(
            '<?xml version="1.0" encoding="UTF-8"?><manifest></manifest>'
        )
        self.assertEqual(manifest.ToDict(), {})

    def test_toxml_omit_local(self):
        """Does not include local_manifests projects when omit_local=True."""
        manifest = self.getXmlManifest(
            '<?xml version="1.0" encoding="UTF-8"?><manifest>'
            '<remote name="a" fetch=".."/><default remote="a" revision="r"/>'
            '<project name="p" groups="local::me"/>'
            '<project name="q"/>'
            '<project name="r" groups="keep"/>'
            "</manifest>"
        )
        self.assertEqual(
            sort_attributes(manifest.ToXml(omit_local=True).toxml()),
            '<?xml version="1.0" ?><manifest>'
            '<remote fetch=".." name="a"/><default remote="a" revision="r"/>'
            '<project name="q"/><project groups="keep" name="r"/></manifest>',
        )

    def test_toxml_with_local(self):
        """Does include local_manifests projects when omit_local=False."""
        manifest = self.getXmlManifest(
            '<?xml version="1.0" encoding="UTF-8"?><manifest>'
            '<remote name="a" fetch=".."/><default remote="a" revision="r"/>'
            '<project name="p" groups="local::me"/>'
            '<project name="q"/>'
            '<project name="r" groups="keep"/>'
            "</manifest>"
        )
        self.assertEqual(
            sort_attributes(manifest.ToXml(omit_local=False).toxml()),
            '<?xml version="1.0" ?><manifest>'
            '<remote fetch=".." name="a"/><default remote="a" revision="r"/>'
            '<project groups="local::me" name="p"/>'
            '<project name="q"/><project groups="keep" name="r"/></manifest>',
        )

    def test_repo_hooks(self):
        """Check repo-hooks settings."""
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="test-remote" fetch="http://localhost" />
  <default remote="test-remote" revision="refs/heads/main" />
  <project name="repohooks" path="src/repohooks"/>
  <repo-hooks in-project="repohooks" enabled-list="a, b"/>
</manifest>
"""
        )
        self.assertEqual(manifest.repo_hooks_project.name, "repohooks")
        self.assertEqual(
            manifest.repo_hooks_project.enabled_repo_hooks, ["a", "b"]
        )

    def test_repo_hooks_unordered(self):
        """Check repo-hooks settings work even if the project def comes second."""  # noqa: E501
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="test-remote" fetch="http://localhost" />
  <default remote="test-remote" revision="refs/heads/main" />
  <repo-hooks in-project="repohooks" enabled-list="a, b"/>
  <project name="repohooks" path="src/repohooks"/>
</manifest>
"""
        )
        self.assertEqual(manifest.repo_hooks_project.name, "repohooks")
        self.assertEqual(
            manifest.repo_hooks_project.enabled_repo_hooks, ["a", "b"]
        )

    def test_unknown_tags(self):
        """Check superproject settings."""
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="test-remote" fetch="http://localhost" />
  <default remote="test-remote" revision="refs/heads/main" />
  <superproject name="superproject"/>
  <iankaz value="unknown (possible) future tags are ignored"/>
  <x-custom-tag>X tags are always ignored</x-custom-tag>
</manifest>
"""
        )
        self.assertEqual(manifest.superproject.name, "superproject")
        self.assertEqual(manifest.superproject.remote.name, "test-remote")
        self.assertEqual(
            sort_attributes(manifest.ToXml().toxml()),
            '<?xml version="1.0" ?><manifest>'
            '<remote fetch="http://localhost" name="test-remote"/>'
            '<default remote="test-remote" revision="refs/heads/main"/>'
            '<superproject name="superproject"/>'
            "</manifest>",
        )

    def test_remote_annotations(self):
        """Check remote settings."""
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="test-remote" fetch="http://localhost">
    <annotation name="foo" value="bar"/>
  </remote>
</manifest>
"""
        )
        self.assertEqual(
            manifest.remotes["test-remote"].annotations[0].name, "foo"
        )
        self.assertEqual(
            manifest.remotes["test-remote"].annotations[0].value, "bar"
        )
        self.assertEqual(
            sort_attributes(manifest.ToXml().toxml()),
            '<?xml version="1.0" ?><manifest>'
            '<remote fetch="http://localhost" name="test-remote">'
            '<annotation name="foo" value="bar"/>'
            "</remote>"
            "</manifest>",
        )

    def test_parse_with_xml_doctype(self):
        """Check correct manifest parse with DOCTYPE node present."""
        manifest = self.getXmlManifest(
            """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE manifest []>
<manifest>
  <remote name="test-remote" fetch="http://localhost" />
  <default remote="test-remote" revision="refs/heads/main" />
  <project name="test-project" path="src/test-project"/>
</manifest>
"""
        )
        self.assertEqual(len(manifest.projects), 1)
        self.assertEqual(manifest.projects[0].name, "test-project")


class IncludeElementTests(ManifestParseTestCase):
    """Tests for <include>."""

    def test_revision_default(self):
        """Check handling of revision attribute."""
        root_m = os.path.join(self.manifest_dir, "root.xml")
        with open(root_m, "w") as fp:
            fp.write(
                """
<manifest>
  <remote name="test-remote" fetch="http://localhost" />
  <default remote="test-remote" revision="refs/heads/main" />
  <include name="stable.xml" revision="stable-branch" />
  <project name="root-name1" path="root-path1" />
  <project name="root-name2" path="root-path2" />
</manifest>
"""
            )
        with open(os.path.join(self.manifest_dir, "stable.xml"), "w") as fp:
            fp.write(
                """
<manifest>
  <project name="stable-name1" path="stable-path1" />
  <project name="stable-name2" path="stable-path2" revision="stable-branch2" />
</manifest>
"""
            )
        include_m = manifest_xml.XmlManifest(self.repodir, root_m)
        for proj in include_m.projects:
            if proj.name == "root-name1":
                # Check include revision not set on root level proj.
                self.assertNotEqual("stable-branch", proj.revisionExpr)
            if proj.name == "root-name2":
                # Check root proj revision not removed.
                self.assertEqual("refs/heads/main", proj.revisionExpr)
            if proj.name == "stable-name1":
                # Check stable proj has inherited revision include node.
                self.assertEqual("stable-branch", proj.revisionExpr)
            if proj.name == "stable-name2":
                # Check stable proj revision can override include node.
                self.assertEqual("stable-branch2", proj.revisionExpr)

    def test_group_levels(self):
        root_m = os.path.join(self.manifest_dir, "root.xml")
        with open(root_m, "w") as fp:
            fp.write(
                """
<manifest>
  <remote name="test-remote" fetch="http://localhost" />
  <default remote="test-remote" revision="refs/heads/main" />
  <include name="level1.xml" groups="level1-group" />
  <project name="root-name1" path="root-path1" />
  <project name="root-name2" path="root-path2" groups="r2g1,r2g2" />
</manifest>
"""
            )
        with open(os.path.join(self.manifest_dir, "level1.xml"), "w") as fp:
            fp.write(
                """
<manifest>
  <include name="level2.xml" groups="level2-group" />
  <project name="level1-name1" path="level1-path1" />
</manifest>
"""
            )
        with open(os.path.join(self.manifest_dir, "level2.xml"), "w") as fp:
            fp.write(
                """
<manifest>
  <project name="level2-name1" path="level2-path1" groups="l2g1,l2g2" />
</manifest>
"""
            )
        include_m = manifest_xml.XmlManifest(self.repodir, root_m)
        for proj in include_m.projects:
            if proj.name == "root-name1":
                # Check include group not set on root level proj.
                self.assertNotIn("level1-group", proj.groups)
            if proj.name == "root-name2":
                # Check root proj group not removed.
                self.assertIn("r2g1", proj.groups)
            if proj.name == "level1-name1":
                # Check level1 proj has inherited group level 1.
                self.assertIn("level1-group", proj.groups)
            if proj.name == "level2-name1":
                # Check level2 proj has inherited group levels 1 and 2.
                self.assertIn("level1-group", proj.groups)
                self.assertIn("level2-group", proj.groups)
                # Check level2 proj group not removed.
                self.assertIn("l2g1", proj.groups)

    def test_allow_bad_name_from_user(self):
        """Check handling of bad name attribute from the user's input."""

        def parse(name):
            name = self.encodeXmlAttr(name)
            manifest = self.getXmlManifest(
                f"""
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <include name="{name}" />
</manifest>
"""
            )
            # Force the manifest to be parsed.
            manifest.ToXml()

        # Setup target of the include.
        target = os.path.join(self.tempdir, "target.xml")
        with open(target, "w") as fp:
            fp.write("<manifest></manifest>")

        # Include with absolute path.
        parse(os.path.abspath(target))

        # Include with relative path.
        parse(os.path.relpath(target, self.manifest_dir))

    def test_bad_name_checks(self):
        """Check handling of bad name attribute."""

        def parse(name):
            name = self.encodeXmlAttr(name)
            # Setup target of the include.
            with open(
                os.path.join(self.manifest_dir, "target.xml"),
                "w",
                encoding="utf-8",
            ) as fp:
                fp.write(f'<manifest><include name="{name}"/></manifest>')

            manifest = self.getXmlManifest(
                """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <include name="target.xml" />
</manifest>
"""
            )
            # Force the manifest to be parsed.
            manifest.ToXml()

        # Handle empty name explicitly because a different codepath rejects it.
        with self.assertRaises(error.ManifestParseError):
            parse("")

        for path in INVALID_FS_PATHS:
            if not path:
                continue

            with self.assertRaises(error.ManifestInvalidPathError):
                parse(path)


class ProjectElementTests(ManifestParseTestCase):
    """Tests for <project>."""

    def test_group(self):
        """Check project group settings."""
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="test-remote" fetch="http://localhost" />
  <default remote="test-remote" revision="refs/heads/main" />
  <project name="test-name" path="test-path"/>
  <project name="extras" path="path" groups="g1,g2,g1"/>
</manifest>
"""
        )
        self.assertEqual(len(manifest.projects), 2)
        # Ordering isn't guaranteed.
        result = {
            manifest.projects[0].name: manifest.projects[0].groups,
            manifest.projects[1].name: manifest.projects[1].groups,
        }
        self.assertCountEqual(
            result["test-name"], ["name:test-name", "all", "path:test-path"]
        )
        self.assertCountEqual(
            result["extras"],
            ["g1", "g2", "g1", "name:extras", "all", "path:path"],
        )
        groupstr = "default,platform-" + platform.system().lower()
        self.assertEqual(groupstr, manifest.GetGroupsStr())
        groupstr = "g1,g2,g1"
        manifest.manifestProject.config.SetString("manifest.groups", groupstr)
        self.assertEqual(groupstr, manifest.GetGroupsStr())

    def test_set_revision_id(self):
        """Check setting of project's revisionId."""
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <project name="test-name"/>
</manifest>
"""
        )
        self.assertEqual(len(manifest.projects), 1)
        project = manifest.projects[0]
        project.SetRevisionId("ABCDEF")
        self.assertEqual(
            sort_attributes(manifest.ToXml().toxml()),
            '<?xml version="1.0" ?><manifest>'
            '<remote fetch="http://localhost" name="default-remote"/>'
            '<default remote="default-remote" revision="refs/heads/main"/>'
            '<project name="test-name" revision="ABCDEF" upstream="refs/heads/main"/>'  # noqa: E501
            "</manifest>",
        )

    def test_trailing_slash(self):
        """Check handling of trailing slashes in attributes."""

        def parse(name, path):
            name = self.encodeXmlAttr(name)
            path = self.encodeXmlAttr(path)
            return self.getXmlManifest(
                f"""
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <project name="{name}" path="{path}" />
</manifest>
"""
            )

        manifest = parse("a/path/", "foo")
        self.assertEqual(
            os.path.normpath(manifest.projects[0].gitdir),
            os.path.join(self.tempdir, ".repo", "projects", "foo.git"),
        )
        self.assertEqual(
            os.path.normpath(manifest.projects[0].objdir),
            os.path.join(
                self.tempdir, ".repo", "project-objects", "a", "path.git"
            ),
        )

        manifest = parse("a/path", "foo/")
        self.assertEqual(
            os.path.normpath(manifest.projects[0].gitdir),
            os.path.join(self.tempdir, ".repo", "projects", "foo.git"),
        )
        self.assertEqual(
            os.path.normpath(manifest.projects[0].objdir),
            os.path.join(
                self.tempdir, ".repo", "project-objects", "a", "path.git"
            ),
        )

        manifest = parse("a/path", "foo//////")
        self.assertEqual(
            os.path.normpath(manifest.projects[0].gitdir),
            os.path.join(self.tempdir, ".repo", "projects", "foo.git"),
        )
        self.assertEqual(
            os.path.normpath(manifest.projects[0].objdir),
            os.path.join(
                self.tempdir, ".repo", "project-objects", "a", "path.git"
            ),
        )

    def test_toplevel_path(self):
        """Check handling of path=. specially."""

        def parse(name, path):
            name = self.encodeXmlAttr(name)
            path = self.encodeXmlAttr(path)
            return self.getXmlManifest(
                f"""
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <project name="{name}" path="{path}" />
</manifest>
"""
            )

        for path in (".", "./", ".//", ".///"):
            manifest = parse("server/path", path)
            self.assertEqual(
                os.path.normpath(manifest.projects[0].gitdir),
                os.path.join(self.tempdir, ".repo", "projects", "..git"),
            )

    def test_bad_path_name_checks(self):
        """Check handling of bad path & name attributes."""

        def parse(name, path):
            name = self.encodeXmlAttr(name)
            path = self.encodeXmlAttr(path)
            manifest = self.getXmlManifest(
                f"""
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <project name="{name}" path="{path}" />
</manifest>
"""
            )
            # Force the manifest to be parsed.
            manifest.ToXml()

        # Verify the parser is valid by default to avoid buggy tests below.
        parse("ok", "ok")

        # Handle empty name explicitly because a different codepath rejects it.
        # Empty path is OK because it defaults to the name field.
        with self.assertRaises(error.ManifestParseError):
            parse("", "ok")

        for path in INVALID_FS_PATHS:
            if not path or path.endswith("/") or path.endswith(os.path.sep):
                continue

            with self.assertRaises(error.ManifestInvalidPathError):
                parse(path, "ok")

            # We have a dedicated test for path=".".
            if path not in {"."}:
                with self.assertRaises(error.ManifestInvalidPathError):
                    parse("ok", path)


class SuperProjectElementTests(ManifestParseTestCase):
    """Tests for <superproject>."""

    def test_superproject(self):
        """Check superproject settings."""
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="test-remote" fetch="http://localhost" />
  <default remote="test-remote" revision="refs/heads/main" />
  <superproject name="superproject"/>
</manifest>
"""
        )
        self.assertEqual(manifest.superproject.name, "superproject")
        self.assertEqual(manifest.superproject.remote.name, "test-remote")
        self.assertEqual(
            manifest.superproject.remote.url, "http://localhost/superproject"
        )
        self.assertEqual(manifest.superproject.revision, "refs/heads/main")
        self.assertEqual(
            sort_attributes(manifest.ToXml().toxml()),
            '<?xml version="1.0" ?><manifest>'
            '<remote fetch="http://localhost" name="test-remote"/>'
            '<default remote="test-remote" revision="refs/heads/main"/>'
            '<superproject name="superproject"/>'
            "</manifest>",
        )

    def test_superproject_revision(self):
        """Check superproject settings with a different revision attribute"""
        self.maxDiff = None
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="test-remote" fetch="http://localhost" />
  <default remote="test-remote" revision="refs/heads/main" />
  <superproject name="superproject" revision="refs/heads/stable" />
</manifest>
"""
        )
        self.assertEqual(manifest.superproject.name, "superproject")
        self.assertEqual(manifest.superproject.remote.name, "test-remote")
        self.assertEqual(
            manifest.superproject.remote.url, "http://localhost/superproject"
        )
        self.assertEqual(manifest.superproject.revision, "refs/heads/stable")
        self.assertEqual(
            sort_attributes(manifest.ToXml().toxml()),
            '<?xml version="1.0" ?><manifest>'
            '<remote fetch="http://localhost" name="test-remote"/>'
            '<default remote="test-remote" revision="refs/heads/main"/>'
            '<superproject name="superproject" revision="refs/heads/stable"/>'
            "</manifest>",
        )

    def test_superproject_revision_default_negative(self):
        """Check superproject settings with a same revision attribute"""
        self.maxDiff = None
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="test-remote" fetch="http://localhost" />
  <default remote="test-remote" revision="refs/heads/stable" />
  <superproject name="superproject" revision="refs/heads/stable" />
</manifest>
"""
        )
        self.assertEqual(manifest.superproject.name, "superproject")
        self.assertEqual(manifest.superproject.remote.name, "test-remote")
        self.assertEqual(
            manifest.superproject.remote.url, "http://localhost/superproject"
        )
        self.assertEqual(manifest.superproject.revision, "refs/heads/stable")
        self.assertEqual(
            sort_attributes(manifest.ToXml().toxml()),
            '<?xml version="1.0" ?><manifest>'
            '<remote fetch="http://localhost" name="test-remote"/>'
            '<default remote="test-remote" revision="refs/heads/stable"/>'
            '<superproject name="superproject"/>'
            "</manifest>",
        )

    def test_superproject_revision_remote(self):
        """Check superproject settings with a same revision attribute"""
        self.maxDiff = None
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="test-remote" fetch="http://localhost" revision="refs/heads/main" />
  <default remote="test-remote" />
  <superproject name="superproject" revision="refs/heads/stable" />
</manifest>
"""  # noqa: E501
        )
        self.assertEqual(manifest.superproject.name, "superproject")
        self.assertEqual(manifest.superproject.remote.name, "test-remote")
        self.assertEqual(
            manifest.superproject.remote.url, "http://localhost/superproject"
        )
        self.assertEqual(manifest.superproject.revision, "refs/heads/stable")
        self.assertEqual(
            sort_attributes(manifest.ToXml().toxml()),
            '<?xml version="1.0" ?><manifest>'
            '<remote fetch="http://localhost" name="test-remote" revision="refs/heads/main"/>'  # noqa: E501
            '<default remote="test-remote"/>'
            '<superproject name="superproject" revision="refs/heads/stable"/>'
            "</manifest>",
        )

    def test_remote(self):
        """Check superproject settings with a remote."""
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <remote name="superproject-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <superproject name="platform/superproject" remote="superproject-remote"/>
</manifest>
"""
        )
        self.assertEqual(manifest.superproject.name, "platform/superproject")
        self.assertEqual(
            manifest.superproject.remote.name, "superproject-remote"
        )
        self.assertEqual(
            manifest.superproject.remote.url,
            "http://localhost/platform/superproject",
        )
        self.assertEqual(manifest.superproject.revision, "refs/heads/main")
        self.assertEqual(
            sort_attributes(manifest.ToXml().toxml()),
            '<?xml version="1.0" ?><manifest>'
            '<remote fetch="http://localhost" name="default-remote"/>'
            '<remote fetch="http://localhost" name="superproject-remote"/>'
            '<default remote="default-remote" revision="refs/heads/main"/>'
            '<superproject name="platform/superproject" remote="superproject-remote"/>'  # noqa: E501
            "</manifest>",
        )

    def test_defalut_remote(self):
        """Check superproject settings with a default remote."""
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <superproject name="superproject" remote="default-remote"/>
</manifest>
"""
        )
        self.assertEqual(manifest.superproject.name, "superproject")
        self.assertEqual(manifest.superproject.remote.name, "default-remote")
        self.assertEqual(manifest.superproject.revision, "refs/heads/main")
        self.assertEqual(
            sort_attributes(manifest.ToXml().toxml()),
            '<?xml version="1.0" ?><manifest>'
            '<remote fetch="http://localhost" name="default-remote"/>'
            '<default remote="default-remote" revision="refs/heads/main"/>'
            '<superproject name="superproject"/>'
            "</manifest>",
        )


class ContactinfoElementTests(ManifestParseTestCase):
    """Tests for <contactinfo>."""

    def test_contactinfo(self):
        """Check contactinfo settings."""
        bugurl = "http://localhost/contactinfo"
        manifest = self.getXmlManifest(
            f"""
<manifest>
  <contactinfo bugurl="{bugurl}"/>
</manifest>
"""
        )
        self.assertEqual(manifest.contactinfo.bugurl, bugurl)
        self.assertEqual(
            manifest.ToXml().toxml(),
            '<?xml version="1.0" ?><manifest>'
            f'<contactinfo bugurl="{bugurl}"/>'
            "</manifest>",
        )


class DefaultElementTests(ManifestParseTestCase):
    """Tests for <default>."""

    def test_default(self):
        """Check default settings."""
        a = manifest_xml._Default()
        a.revisionExpr = "foo"
        a.remote = manifest_xml._XmlRemote(name="remote")
        b = manifest_xml._Default()
        b.revisionExpr = "bar"
        self.assertEqual(a, a)
        self.assertNotEqual(a, b)
        self.assertNotEqual(b, a.remote)
        self.assertNotEqual(a, 123)
        self.assertNotEqual(a, None)


class RemoteElementTests(ManifestParseTestCase):
    """Tests for <remote>."""

    def test_remote(self):
        """Check remote settings."""
        a = manifest_xml._XmlRemote(name="foo")
        a.AddAnnotation("key1", "value1", "true")
        b = manifest_xml._XmlRemote(name="foo")
        b.AddAnnotation("key2", "value1", "true")
        c = manifest_xml._XmlRemote(name="foo")
        c.AddAnnotation("key1", "value2", "true")
        d = manifest_xml._XmlRemote(name="foo")
        d.AddAnnotation("key1", "value1", "false")
        self.assertEqual(a, a)
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(a, d)
        self.assertNotEqual(a, manifest_xml._Default())
        self.assertNotEqual(a, 123)
        self.assertNotEqual(a, None)


class RemoveProjectElementTests(ManifestParseTestCase):
    """Tests for <remove-project>."""

    def test_remove_one_project(self):
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <project name="myproject" />
  <remove-project name="myproject" />
</manifest>
"""
        )
        self.assertEqual(manifest.projects, [])

    def test_remove_one_project_one_remains(self):
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <project name="myproject" />
  <project name="yourproject" />
  <remove-project name="myproject" />
</manifest>
"""
        )

        self.assertEqual(len(manifest.projects), 1)
        self.assertEqual(manifest.projects[0].name, "yourproject")

    def test_remove_one_project_doesnt_exist(self):
        with self.assertRaises(manifest_xml.ManifestParseError):
            manifest = self.getXmlManifest(
                """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <remove-project name="myproject" />
</manifest>
"""
            )
            manifest.projects

    def test_remove_one_optional_project_doesnt_exist(self):
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <remove-project name="myproject" optional="true" />
</manifest>
"""
        )
        self.assertEqual(manifest.projects, [])

    def test_remove_using_path_attrib(self):
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <project name="project1" path="tests/path1" />
  <project name="project1" path="tests/path2" />
  <project name="project2" />
  <project name="project3" />
  <project name="project4" path="tests/path3" />
  <project name="project4" path="tests/path4" />
  <project name="project5" />
  <project name="project6" path="tests/path6" />

  <remove-project name="project1" path="tests/path2" />
  <remove-project name="project3" />
  <remove-project name="project4" />
  <remove-project path="project5" />
  <remove-project path="tests/path6" />
</manifest>
"""
        )
        found_proj1_path1 = False
        found_proj2 = False
        for proj in manifest.projects:
            if proj.name == "project1":
                found_proj1_path1 = True
                self.assertEqual(proj.relpath, "tests/path1")
            if proj.name == "project2":
                found_proj2 = True
            self.assertNotEqual(proj.name, "project3")
            self.assertNotEqual(proj.name, "project4")
            self.assertNotEqual(proj.name, "project5")
            self.assertNotEqual(proj.name, "project6")
        self.assertTrue(found_proj1_path1)
        self.assertTrue(found_proj2)

    def test_base_revision_checks_on_patching(self):
        manifest_fail_wrong_tag = self.getXmlManifest(
            """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="tag.002" />
  <project name="project1" path="tests/path1" />
  <extend-project name="project1" revision="new_hash" base-rev="tag.001" />
</manifest>
"""
        )
        with self.assertRaises(error.ManifestParseError):
            manifest_fail_wrong_tag.ToXml()

        manifest_fail_remove = self.getXmlManifest(
            """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <project name="project1" path="tests/path1" revision="hash1" />
  <remove-project name="project1" base-rev="wrong_hash" />
</manifest>
"""
        )
        with self.assertRaises(error.ManifestParseError):
            manifest_fail_remove.ToXml()

        manifest_fail_extend = self.getXmlManifest(
            """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <project name="project1" path="tests/path1" revision="hash1" />
  <extend-project name="project1" revision="new_hash" base-rev="wrong_hash" />
</manifest>
"""
        )
        with self.assertRaises(error.ManifestParseError):
            manifest_fail_extend.ToXml()

        manifest_fail_unknown = self.getXmlManifest(
            """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <project name="project1" path="tests/path1" />
  <extend-project name="project1" revision="new_hash" base-rev="any_hash" />
</manifest>
"""
        )
        with self.assertRaises(error.ManifestParseError):
            manifest_fail_unknown.ToXml()

        manifest_ok = self.getXmlManifest(
            """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <project name="project1" path="tests/path1" revision="hash1" />
  <project name="project2" path="tests/path2" revision="hash2" />
  <project name="project3" path="tests/path3" revision="hash3" />
  <project name="project4" path="tests/path4" revision="hash4" />

  <remove-project name="project1" />
  <remove-project name="project2" base-rev="hash2" />
  <project name="project2" path="tests/path2" revision="new_hash2" />
  <extend-project name="project3" base-rev="hash3" revision="new_hash3" />
  <extend-project name="project3" base-rev="new_hash3" revision="newer_hash3" />
  <remove-project path="tests/path4" base-rev="hash4" />
</manifest>
"""
        )
        found_proj2 = False
        found_proj3 = False
        for proj in manifest_ok.projects:
            if proj.name == "project2":
                found_proj2 = True
            if proj.name == "project3":
                found_proj3 = True
            self.assertNotEqual(proj.name, "project1")
            self.assertNotEqual(proj.name, "project4")
        self.assertTrue(found_proj2)
        self.assertTrue(found_proj3)
        self.assertTrue(len(manifest_ok.projects) == 2)


class ExtendProjectElementTests(ManifestParseTestCase):
    """Tests for <extend-project>."""

    def test_extend_project_dest_path_single_match(self):
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <project name="myproject" />
  <extend-project name="myproject" dest-path="bar" />
</manifest>
"""
        )
        self.assertEqual(len(manifest.projects), 1)
        self.assertEqual(manifest.projects[0].relpath, "bar")

    def test_extend_project_dest_path_multi_match(self):
        with self.assertRaises(manifest_xml.ManifestParseError):
            manifest = self.getXmlManifest(
                """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <project name="myproject" path="x" />
  <project name="myproject" path="y" />
  <extend-project name="myproject" dest-path="bar" />
</manifest>
"""
            )
            manifest.projects

    def test_extend_project_dest_path_multi_match_path_specified(self):
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <project name="myproject" path="x" />
  <project name="myproject" path="y" />
  <extend-project name="myproject" path="x" dest-path="bar" />
</manifest>
"""
        )
        self.assertEqual(len(manifest.projects), 2)
        if manifest.projects[0].relpath == "y":
            self.assertEqual(manifest.projects[1].relpath, "bar")
        else:
            self.assertEqual(manifest.projects[0].relpath, "bar")
            self.assertEqual(manifest.projects[1].relpath, "y")

    def test_extend_project_dest_branch(self):
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" dest-branch="foo" />
  <project name="myproject" />
  <extend-project name="myproject" dest-branch="bar" />
</manifest>
"""  # noqa: E501
        )
        self.assertEqual(len(manifest.projects), 1)
        self.assertEqual(manifest.projects[0].dest_branch, "bar")

    def test_extend_project_upstream(self):
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="default-remote" fetch="http://localhost" />
  <default remote="default-remote" revision="refs/heads/main" />
  <project name="myproject" />
  <extend-project name="myproject" upstream="bar" />
</manifest>
"""
        )
        self.assertEqual(len(manifest.projects), 1)
        self.assertEqual(manifest.projects[0].upstream, "bar")


class NormalizeUrlTests(ManifestParseTestCase):
    """Tests for normalize_url() in manifest_xml.py"""

    def test_has_trailing_slash(self):
        url = "http://foo.com/bar/baz/"
        self.assertEqual(
            "http://foo.com/bar/baz", manifest_xml.normalize_url(url)
        )

        url = "http://foo.com/bar/"
        self.assertEqual("http://foo.com/bar", manifest_xml.normalize_url(url))

    def test_has_leading_slash(self):
        """SCP-like syntax except a / comes before the : which git disallows."""
        url = "/git@foo.com:bar/baf"
        self.assertEqual(url, manifest_xml.normalize_url(url))

        url = "gi/t@foo.com:bar/baf"
        self.assertEqual(url, manifest_xml.normalize_url(url))

        url = "git@fo/o.com:bar/baf"
        self.assertEqual(url, manifest_xml.normalize_url(url))

    def test_has_no_scheme(self):
        """Deal with cases where we have no scheme, but we also
        aren't dealing with the git SCP-like syntax
        """
        url = "foo.com/baf/bat"
        self.assertEqual(url, manifest_xml.normalize_url(url))

        url = "foo.com/baf"
        self.assertEqual(url, manifest_xml.normalize_url(url))

        url = "git@foo.com/baf/bat"
        self.assertEqual(url, manifest_xml.normalize_url(url))

        url = "git@foo.com/baf"
        self.assertEqual(url, manifest_xml.normalize_url(url))

        url = "/file/path/here"
        self.assertEqual(url, manifest_xml.normalize_url(url))

    def test_has_no_scheme_matches_scp_like_syntax(self):
        url = "git@foo.com:bar/baf"
        self.assertEqual(
            "ssh://git@foo.com/bar/baf", manifest_xml.normalize_url(url)
        )

        url = "git@foo.com:bar/"
        self.assertEqual(
            "ssh://git@foo.com/bar", manifest_xml.normalize_url(url)
        )

    def test_remote_url_resolution(self):
        remote = manifest_xml._XmlRemote(
            name="foo",
            fetch="git@github.com:org2/",
            manifestUrl="git@github.com:org2/custom_manifest.git",
        )
        self.assertEqual("ssh://git@github.com/org2", remote.resolvedFetchUrl)

        remote = manifest_xml._XmlRemote(
            name="foo",
            fetch="ssh://git@github.com/org2/",
            manifestUrl="git@github.com:org2/custom_manifest.git",
        )
        self.assertEqual("ssh://git@github.com/org2", remote.resolvedFetchUrl)

        remote = manifest_xml._XmlRemote(
            name="foo",
            fetch="git@github.com:org2/",
            manifestUrl="ssh://git@github.com/org2/custom_manifest.git",
        )
        self.assertEqual("ssh://git@github.com/org2", remote.resolvedFetchUrl)


class CheckLocalPathAbsOkTests(unittest.TestCase):
    """Tests for the abs_ok parameter on _CheckLocalPath().

    Spec reference: Section 17.1 — Absolute Linkfile Dest.

    When abs_ok=True, absolute paths should pass validation.
    When abs_ok=False (default), absolute paths should be rejected.
    Bad components (.git, .repo, ..) and bad Unicode codepoints must
    still be rejected regardless of abs_ok.
    """

    ABSOLUTE_PATHS = (
        "/home/user/.claude-marketplaces/foo",
        "/opt/plugins/bar",
        "/tmp/test-dest",
    )

    def test_spec_17_1_abs_ok_parameter_default_false(self):
        """_CheckLocalPath rejects absolute paths by default.

        Given: _CheckLocalPath called without abs_ok (default False).
        When: Called with an absolute path.
        Then: Returns an error message (not None).
        Spec: Section 17.1 — backward compatibility.
        """
        for path in self.ABSOLUTE_PATHS:
            msg = manifest_xml.XmlManifest._CheckLocalPath(path)
            self.assertIsNotNone(
                msg,
                f"absolute path '{path}' should be rejected by default",
            )

    def test_spec_17_1_absolute_dest_accepted_linkfile(self):
        """_CheckLocalPath accepts absolute paths when abs_ok=True.

        Given: _CheckLocalPath called with abs_ok=True.
        When: Called with a valid absolute path.
        Then: Returns None (no error).
        Spec: Section 17.1 — absolute dest accepted for linkfile.
        """
        for path in self.ABSOLUTE_PATHS:
            msg = manifest_xml.XmlManifest._CheckLocalPath(path, abs_ok=True)
            self.assertIsNone(
                msg,
                f"absolute path '{path}' should be accepted with abs_ok=True",
            )

    def test_spec_17_1_absolute_dest_rejected_copyfile(self):
        """_ValidateFilePaths rejects absolute dest for copyfile.

        Given: _ValidateFilePaths called for copyfile element.
        When: dest is an absolute path.
        Then: ManifestInvalidPathError is raised.
        Spec: Section 17.1 — copyfile dest remains restricted.
        """
        for path in self.ABSOLUTE_PATHS:
            with self.assertRaises(
                error.ManifestInvalidPathError,
                msg=f"copyfile absolute dest '{path}' should be rejected",
            ):
                manifest_xml.XmlManifest._ValidateFilePaths(
                    "copyfile", "foo", path
                )

    def test_spec_17_1_bad_component_git_rejected_abs(self):
        """_CheckLocalPath rejects .git component in absolute paths.

        Given: _CheckLocalPath called with abs_ok=True.
        When: Path contains a .git component.
        Then: Returns an error message.
        Spec: Section 17.1 — bad components still rejected.
        """
        bad_paths = (
            "/home/.git/foo",
            "/opt/.git/bar",
            "/home/user/.GIT/baz",
        )
        for path in bad_paths:
            msg = manifest_xml.XmlManifest._CheckLocalPath(path, abs_ok=True)
            self.assertIsNotNone(
                msg,
                f"path with .git component '{path}' should be rejected",
            )

    def test_spec_17_1_bad_component_repo_rejected_abs(self):
        """_CheckLocalPath rejects .repo component in absolute paths.

        Given: _CheckLocalPath called with abs_ok=True.
        When: Path contains a .repo component.
        Then: Returns an error message.
        Spec: Section 17.1 — bad components still rejected.
        """
        bad_paths = (
            "/home/.repo/foo",
            "/opt/.repoconfig/bar",
        )
        for path in bad_paths:
            msg = manifest_xml.XmlManifest._CheckLocalPath(path, abs_ok=True)
            self.assertIsNotNone(
                msg,
                f"path with .repo component '{path}' should be rejected",
            )

    def test_spec_17_1_bad_component_dotdot_rejected_abs(self):
        """_CheckLocalPath rejects .. component in absolute paths.

        Given: _CheckLocalPath called with abs_ok=True.
        When: Path contains a .. component.
        Then: Returns an error message.
        Spec: Section 17.1 — bad components still rejected.
        """
        bad_paths = (
            "/home/../etc/passwd",
            "/opt/foo/../../bar",
        )
        for path in bad_paths:
            msg = manifest_xml.XmlManifest._CheckLocalPath(path, abs_ok=True)
            self.assertIsNotNone(
                msg,
                f"path with .. component '{path}' should be rejected",
            )

    def test_spec_17_1_bad_codepoint_rejected_abs(self):
        """_CheckLocalPath rejects bad Unicode codepoints in absolute paths.

        Given: _CheckLocalPath called with abs_ok=True.
        When: Path contains Unicode combining/directional characters.
        Then: Returns an error message.
        Spec: Section 17.1 — bad codepoints still rejected.
        """
        bad_paths = (
            "/home/foo\u200cbar",
            "/opt/\u202ebar",
            "/tmp/\u200dtest",
        )
        for path in bad_paths:
            msg = manifest_xml.XmlManifest._CheckLocalPath(path, abs_ok=True)
            self.assertIsNotNone(
                msg,
                f"path with bad codepoint '{repr(path)}' should be rejected",
            )


class CheckLocalPathAbsOkEdgeCaseTests(unittest.TestCase):
    """Edge case tests for the abs_ok parameter on _CheckLocalPath().

    Spec reference: Section 17.1 — Absolute Linkfile Dest.

    Covers: valid unicode in absolute paths, .git at various positions,
    deeply nested paths, trailing/double slashes, empty components,
    and paths that normalize to contain bad components.
    """

    TRAILING_SLASH_PATHS = (
        "/home/user/plugins/",
        "/opt/marketplace/",
    )

    def test_spec_17_1_unicode_valid_abs_path(self):
        """Valid unicode characters in absolute paths are accepted.

        Given: _CheckLocalPath called with abs_ok=True.
        When: Path contains valid (non-dangerous) unicode characters.
        Then: Returns None (no error).
        Spec: Section 17.1 — unicode edge case.
        """
        valid_unicode_paths = (
            "/home/ユーザー/plugins/foo",
            "/opt/café/bar",
            "/tmp/données/test",
        )
        for path in valid_unicode_paths:
            with self.subTest(path=path):
                msg = manifest_xml.XmlManifest._CheckLocalPath(
                    path, abs_ok=True
                )
                self.assertIsNone(
                    msg,
                    f"valid unicode path '{path}' should be accepted",
                )

    def test_spec_17_1_unicode_bad_codepoint_abs_path(self):
        """Bad unicode codepoints in absolute paths are rejected.

        Given: _CheckLocalPath called with abs_ok=True.
        When: Path contains dangerous unicode codepoints (ZWNJ, RLO, etc.).
        Then: Returns an error message.
        Spec: Section 17.1 — bad codepoints always rejected.
        """
        bad_unicode_paths = (
            "/home/\u200cfoo",
            "/opt/\u202ebar",
            "/tmp/\ufeffbaz",
            "/home/\u206afoo",
        )
        for path in bad_unicode_paths:
            with self.subTest(path=repr(path)):
                msg = manifest_xml.XmlManifest._CheckLocalPath(
                    path, abs_ok=True
                )
                self.assertIsNotNone(
                    msg,
                    f"bad unicode path '{repr(path)}' should be rejected",
                )

    def test_spec_17_1_git_component_various_positions(self):
        """.git component rejected at any position in absolute paths.

        Given: _CheckLocalPath called with abs_ok=True.
        When: .git appears at different positions in the path.
        Then: Returns an error message for all positions.
        Spec: Section 17.1 — .git always rejected.
        """
        git_at_positions = (
            "/.git/foo/bar",
            "/home/.git/foo",
            "/home/user/.git",
            "/a/b/c/.git/d/e",
        )
        for path in git_at_positions:
            with self.subTest(path=path):
                msg = manifest_xml.XmlManifest._CheckLocalPath(
                    path, abs_ok=True
                )
                self.assertIsNotNone(
                    msg,
                    f".git at '{path}' should be rejected",
                )

    def test_spec_17_1_deeply_nested_abs_path(self):
        """Deeply nested absolute paths are accepted when valid.

        Given: _CheckLocalPath called with abs_ok=True.
        When: Path is deeply nested but contains no bad components.
        Then: Returns None (no error).
        Spec: Section 17.1 — deep nesting edge case.
        """
        deep_paths = (
            "/a/b/c/d/e/f/g/h/i/j/k/l/m/n/o/p",
            "/home/user/.claude-marketplaces/v1/plugins/foo/bar/baz",
        )
        for path in deep_paths:
            with self.subTest(path=path):
                msg = manifest_xml.XmlManifest._CheckLocalPath(
                    path, abs_ok=True
                )
                self.assertIsNone(
                    msg,
                    f"deep valid path '{path}' should be accepted",
                )

    def test_spec_17_1_trailing_slash_abs_path(self):
        """Absolute paths with trailing slashes accepted with dir_ok.

        Given: _CheckLocalPath called with abs_ok=True, dir_ok=True.
        When: Path has a trailing slash.
        Then: Returns None when dir_ok=True.
        Spec: Section 17.1 — trailing slash edge case.
        """
        for path in self.TRAILING_SLASH_PATHS:
            with self.subTest(path=path):
                msg = manifest_xml.XmlManifest._CheckLocalPath(
                    path, abs_ok=True, dir_ok=True
                )
                self.assertIsNone(
                    msg,
                    f"trailing slash path '{path}' should be accepted "
                    f"with dir_ok=True",
                )

    def test_spec_17_1_trailing_slash_rejected_without_dir_ok(self):
        """Absolute paths with trailing slashes rejected without dir_ok.

        Given: _CheckLocalPath called with abs_ok=True, dir_ok=False.
        When: Path has a trailing slash.
        Then: Returns an error message.
        Spec: Section 17.1 — dir_ok interaction.
        """
        for path in self.TRAILING_SLASH_PATHS:
            with self.subTest(path=path):
                msg = manifest_xml.XmlManifest._CheckLocalPath(
                    path, abs_ok=True
                )
                self.assertIsNotNone(
                    msg,
                    f"trailing slash path '{path}' should be rejected "
                    f"without dir_ok",
                )

    def test_spec_17_1_double_slash_abs_path(self):
        """Absolute paths with double slashes are accepted.

        Given: _CheckLocalPath called with abs_ok=True.
        When: Path contains double slashes (empty components).
        Then: Returns None (double slashes produce empty parts stripped
              by rstrip, not treated as bad components).
        Spec: Section 17.1 — double slash edge case.
        """
        double_slash_paths = (
            "/home//user/foo",
            "/opt///plugins/bar",
        )
        for path in double_slash_paths:
            with self.subTest(path=path):
                msg = manifest_xml.XmlManifest._CheckLocalPath(
                    path, abs_ok=True
                )
                self.assertIsNone(
                    msg,
                    f"double slash path '{path}' should be accepted",
                )

    def test_spec_17_1_normalized_bad_component_abs(self):
        """Paths normalizing to bad components are rejected.

        Given: _CheckLocalPath called with abs_ok=True.
        When: Path contains .. that, after normalization, still leaves
              a bad component like .git or .repo.
        Then: Returns an error message.
        Spec: Section 17.1 — normalization edge case.
        """
        normalized_bad_paths = (
            "/foo/../.git/bar",
            "/home/user/../.repo/config",
        )
        for path in normalized_bad_paths:
            with self.subTest(path=path):
                msg = manifest_xml.XmlManifest._CheckLocalPath(
                    path, abs_ok=True
                )
                self.assertIsNotNone(
                    msg,
                    f"normalized bad path '{path}' should be rejected",
                )


class EnvsubstAbsoluteLinkfileIntegrationTest(unittest.TestCase):
    """Integration test: envsubst + manifest validation + absolute linkfile.

    Spec reference: Section 17.1 — End-to-end flow.

    Exercises the complete pipeline:
    1. Environment variable resolution (os.path.expandvars, same as envsubst)
    2. Manifest path validation (_ValidateFilePaths with abs_ok=True)
    3. Symlink creation (_LinkFile._Link with absolute dest)

    This validates that the three components (envsubst, manifest_xml,
    project._LinkFile) work together when a linkfile dest contains an
    environment variable that expands to an absolute path.

    Verified: E1-F1-S4-T2 — all assertions pass with E1-F1-S1 + S2 in place.
    """

    ENV_VAR_NAME = "CLAUDE_MARKETPLACES_DIR"

    def setUp(self):
        self.tempdirobj = tempfile.TemporaryDirectory(prefix="repo_tests")
        self.tempdir = self.tempdirobj.name
        # Simulated worktree and topdir for _LinkFile.
        self.worktree = os.path.join(self.tempdir, "git-project")
        self.topdir = os.path.join(self.tempdir, "checkout")
        os.makedirs(self.worktree)
        os.makedirs(self.topdir)
        # Absolute dest directory (simulates CLAUDE_MARKETPLACES_DIR).
        self.marketplace_dir = os.path.join(self.tempdir, "marketplaces")
        # Set the env var for expandvars resolution.
        self.orig_env = os.environ.get(self.ENV_VAR_NAME)
        os.environ[self.ENV_VAR_NAME] = self.marketplace_dir

    def tearDown(self):
        # Restore original env state.
        if self.orig_env is None:
            os.environ.pop(self.ENV_VAR_NAME, None)
        else:
            os.environ[self.ENV_VAR_NAME] = self.orig_env
        self.tempdirobj.cleanup()

    def _create_source_file(self, name):
        """Create a source file in the simulated worktree."""
        path = os.path.join(self.worktree, name)
        with open(path, "w") as f:
            f.write(name)
        return path

    def test_spec_17_1_integration_envsubst_absolute_linkfile_e2e(self):
        """End-to-end: envsubst resolves variable, manifest validates, symlink created.

        Given: CLAUDE_MARKETPLACES_DIR is set to a temporary directory.
        And: A linkfile dest attribute contains ${CLAUDE_MARKETPLACES_DIR}/mkt.
        When: The variable is resolved via os.path.expandvars (envsubst).
        And: The expanded path passes _ValidateFilePaths as a linkfile dest.
        And: _LinkFile._Link() creates the symlink at the absolute path.
        Then: The symlink exists at the resolved absolute path.
        And: Parent directories were created.
        Spec: Section 17.1 — envsubst + absolute linkfile integration.
        """
        src_name = "settings.yml"
        self._create_source_file(src_name)

        # Step 1: Simulate envsubst — resolve ${CLAUDE_MARKETPLACES_DIR}.
        raw_dest = "${%s}/test-marketplace" % self.ENV_VAR_NAME
        resolved_dest = os.path.expandvars(raw_dest)
        self.assertTrue(
            os.path.isabs(resolved_dest),
            f"resolved dest '{resolved_dest}' should be absolute",
        )
        self.assertNotIn(
            "$",
            resolved_dest,
            "all variables should be resolved",
        )

        # Step 2: Validate through manifest parsing layer.
        # This calls _CheckLocalPath with abs_ok=True for linkfile.
        manifest_xml.XmlManifest._ValidateFilePaths(
            "linkfile", src_name, resolved_dest
        )

        # Step 3: Create the symlink via _LinkFile._Link().
        lf = project._LinkFile(
            self.worktree, src_name, self.topdir, resolved_dest
        )
        lf._Link()

        # Step 4: Verify symlink exists at the resolved absolute path.
        self.assertTrue(
            os.path.islink(resolved_dest),
            f"symlink should exist at '{resolved_dest}'",
        )
        self.assertTrue(
            os.path.exists(resolved_dest),
            f"symlink target should be resolvable at '{resolved_dest}'",
        )

        # Step 5: Verify parent directories were created.
        parent_dir = os.path.dirname(resolved_dest)
        self.assertTrue(
            os.path.isdir(parent_dir),
            f"parent dir '{parent_dir}' should exist",
        )


class MultipleCheckoutsSameRepoTests(ManifestParseTestCase):
    """Verification tests for multiple independent checkouts of the same repo.

    Spec reference: Section 17.3 — Existing behaviors to preserve.

    The fork must not break the ability to declare the same repository
    multiple times in a manifest with different paths and revisions.
    Each entry becomes an independent Project instance.
    """

    def test_spec_17_3_multiple_checkouts_same_repo(self):
        """Multiple <project> entries for same repo parse as independent projects.

        Given: A manifest with two <project> entries referencing the same
            remote repo name but different paths and revisions.
        When: The manifest is parsed.
        Then: Two independent Project objects are created with distinct
            paths and revisions.
        Spec: Section 17.3 — multiple independent checkouts preserved.
        """
        manifest = self.getXmlManifest(
            """
<manifest>
  <remote name="test-remote" fetch="http://localhost" />
  <default remote="test-remote" revision="refs/heads/main" />
  <project name="shared-repo" path="checkout-a"
           revision="refs/tags/v1.0.0" />
  <project name="shared-repo" path="checkout-b"
           revision="refs/tags/v2.0.0" />
</manifest>
"""
        )
        self.assertEqual(
            len(manifest.projects),
            2,
            "Manifest should contain exactly 2 project entries",
        )

        projects_by_path = {p.relpath: p for p in manifest.projects}
        self.assertIn("checkout-a", projects_by_path)
        self.assertIn("checkout-b", projects_by_path)

        proj_a = projects_by_path["checkout-a"]
        proj_b = projects_by_path["checkout-b"]

        # Same repo name but different paths.
        self.assertEqual(proj_a.name, "shared-repo")
        self.assertEqual(proj_b.name, "shared-repo")
        self.assertNotEqual(
            proj_a.relpath,
            proj_b.relpath,
            "Projects should have different checkout paths",
        )

        # Different revisions.
        self.assertEqual(proj_a.revisionExpr, "refs/tags/v1.0.0")
        self.assertEqual(proj_b.revisionExpr, "refs/tags/v2.0.0")


class CircularIncludeDetectionTests(ManifestParseTestCase):
    """Verification tests for circular <include> detection.

    Spec reference: Section 17.3 — Existing behaviors to preserve.
    When a manifest includes itself (directly or indirectly), the parser
    must detect the cycle via Python's recursion limit and raise an error
    rather than recursing infinitely.
    """

    def test_spec_17_3_circular_include_detection(self):
        """Verify circular <include> raises an error (spec 17.3).

        A manifest file that includes itself must trigger a RecursionError
        (subclass of RuntimeError) when the manifest is loaded.
        """
        import sys

        # Create a manifest that includes itself.
        inc_a = os.path.join(self.manifest_dir, "a.xml")
        with open(inc_a, "w") as fp:
            fp.write(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<manifest>\n  <include name="a.xml" />\n</manifest>\n'
            )

        manifest = self.getXmlManifest(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<manifest>\n"
            '  <remote name="test-remote" fetch="http://localhost" />\n'
            '  <default remote="test-remote" revision="refs/heads/main" />\n'
            '  <include name="a.xml" />\n'
            "</manifest>\n"
        )

        # Lower the recursion limit to make the test fast, then restore it.
        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(200)
        try:
            with self.assertRaises(RuntimeError):
                # Accessing .projects forces _Load which triggers parsing.
                _ = manifest.projects
        finally:
            sys.setrecursionlimit(old_limit)
