#!/usr/bin/env python3
"""Worktrees: base detection, create, remove, and the rail snapshots."""

import os
import stat
import unittest

from helpers import Sandbox, main

from bottega import worktree
from bottega.util import Refused, UsageError


class Base(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(self)
        self.ctx = self.box.active()
        self.ctx.__enter__()
        self.addCleanup(self.ctx.__exit__, None, None, None)

    def test_origin_head_wins(self):
        repo = self.box.make_repo()
        self.assertEqual(worktree.detect_base(repo), ("main", "origin/main"))

    def test_origin_head_on_another_branch(self):
        repo = self.box.make_repo(branch="trunk")
        self.box.git("branch", "main", cwd=repo)
        self.assertEqual(worktree.detect_base(repo), ("trunk", "origin/trunk"))

    def test_falls_back_to_main_then_master(self):
        repo = self.box.make_repo(origin=False)
        self.assertEqual(worktree.detect_base(repo), ("main", "main"))
        legacy = self.box.make_repo("legacy", origin=False, branch="master")
        self.assertEqual(worktree.detect_base(legacy), ("master", "master"))

    def test_origin_without_head_falls_back(self):
        repo = self.box.make_repo()
        self.box.git("remote", "set-head", "origin", "--delete", cwd=repo)
        self.assertEqual(worktree.detect_base(repo), ("main", "main"))

    def test_no_candidate_is_refused(self):
        repo = self.box.make_repo(origin=False, branch="trunk")
        with self.assertRaises(Refused):
            worktree.detect_base(repo)

    def test_explicit_base(self):
        repo = self.box.make_repo()
        self.box.git("branch", "develop", cwd=repo)
        self.assertEqual(worktree.detect_base(repo, "develop"), ("develop", "develop"))
        self.assertEqual(
            worktree.detect_base(repo, "origin/main"), ("main", "origin/main")
        )
        with self.assertRaises(Refused):
            worktree.detect_base(repo, "nope")

    def test_repo_root(self):
        repo = self.box.make_repo(files={"src/a.py": "x\n"})
        self.assertEqual(worktree.repo_root(repo / "src"), repo)
        with self.assertRaises(UsageError):
            worktree.repo_root(self.box.work)


class CreateRemove(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(self)
        self.ctx = self.box.active()
        self.ctx.__enter__()
        self.addCleanup(self.ctx.__exit__, None, None, None)
        self.repo = self.box.make_repo()

    def test_create_is_a_sibling_on_a_new_branch_from_the_base(self):
        path, branch = worktree.create(self.repo, "20261017-0900-x", "origin/main")
        self.assertEqual(path, self.repo.parent / "app-worktrees" / "20261017-0900-x")
        self.assertEqual(branch, "bottega/20261017-0900-x")
        self.assertTrue((path / "README.md").is_file())
        self.assertEqual(
            self.box.git("rev-parse", "--abbrev-ref", "HEAD", cwd=path), branch
        )
        self.assertEqual(
            self.box.git("rev-parse", "HEAD", cwd=path),
            self.box.git("rev-parse", "origin/main", cwd=self.repo),
        )

    def test_create_refuses_an_existing_path_or_branch(self):
        worktree.create(self.repo, "t1", "main")
        with self.assertRaises(Refused):
            worktree.create(self.repo, "t1", "main")
        self.box.git("branch", "bottega/t2", cwd=self.repo)
        with self.assertRaises(Refused):
            worktree.create(self.repo, "t2", "main")

    def test_the_projects_post_checkout_hook_provisions(self):
        hook = self.repo / ".git" / "hooks" / "post-checkout"
        hook.write_text("#!/bin/sh\necho provisioned > .provisioned\n")
        hook.chmod(hook.stat().st_mode | stat.S_IEXEC)
        path, _ = worktree.create(self.repo, "t3", "main")
        self.assertEqual((path / ".provisioned").read_text(), "provisioned\n")

    def test_remove_deletes_worktree_and_branch(self):
        path, branch = worktree.create(self.repo, "t4", "main")
        (path / "README.md").write_text("dirty\n")
        (path / "new.txt").write_text("untracked\n")
        done = worktree.remove(self.repo, path, branch)
        self.assertEqual(len(done), 2)
        self.assertFalse(path.exists())
        self.assertFalse(worktree.branch_exists(self.repo, branch))
        self.assertFalse(path.parent.exists())  # empty -worktrees dir removed
        self.assertEqual(worktree.remove(self.repo, path, branch), [])

    def test_remove_tolerates_a_worktree_deleted_by_hand(self):
        path, branch = worktree.create(self.repo, "t5", "main")
        self.box.git("worktree", "remove", "--force", str(path), cwd=self.repo)
        self.assertEqual(
            worktree.remove(self.repo, path, branch), ["deleted branch " + branch]
        )


class Rails(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(self)
        self.ctx = self.box.active()
        self.ctx.__enter__()
        self.addCleanup(self.ctx.__exit__, None, None, None)
        repo = self.box.make_repo(files={"a.txt": "a\n", ".gitignore": "cache/\n"})
        self.path, _ = worktree.create(repo, "t", "main")
        self.before = worktree.snapshot(self.path)

    def after(self):
        return worktree.rails(self.before, worktree.snapshot(self.path))

    def test_nothing_changed(self):
        self.assertFalse(worktree.changed(self.after()))

    def test_tracked_edit_changes_the_diff(self):
        (self.path / "a.txt").write_text("b\n")
        self.assertTrue(worktree.changed(self.after()))

    def test_staged_edit_changes_the_diff(self):
        (self.path / "a.txt").write_text("b\n")
        self.box.git("add", "a.txt", cwd=self.path)
        self.assertTrue(worktree.changed(self.after()))

    def test_untracked_files_are_recorded_not_a_change(self):
        (self.path / "notes.txt").write_text("x\n")
        os.makedirs(self.path / "cache")
        (self.path / "cache" / "ignored").write_text("x\n")
        rail = self.after()
        self.assertFalse(worktree.changed(rail))
        self.assertEqual(rail["new_untracked"], ["notes.txt"])

    def test_commit_changes_head(self):
        (self.path / "a.txt").write_text("b\n")
        self.box.git("commit", "-qam", "change", cwd=self.path)
        rail = self.after()
        self.assertTrue(worktree.changed(rail))
        self.assertNotEqual(rail["head_before"], rail["head_after"])
        self.assertEqual(rail["diff_sha_before"], rail["diff_sha_after"])


if __name__ == "__main__":
    main()
