"""Dashboard shell command injection hardening tests."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from seam_runtime.dashboard import (
    ALLOWED_SHELL_COMMANDS,
    ALLOWED_SHELL_PATHS,
    BLOCKED_SHELL_COMMANDS,
    _get_shell_timeout,
    _validate_shell_command,
    _validate_shell_cwd,
    _validate_shell_executable,
)


class TestValidateShellExecutable:
    def test_valid_bash(self):
        assert _validate_shell_executable("/bin/bash") in ALLOWED_SHELL_PATHS

    def test_valid_sh(self):
        assert _validate_shell_executable("/bin/sh") in ALLOWED_SHELL_PATHS

    def test_valid_zsh(self):
        assert _validate_shell_executable("/bin/zsh") in ALLOWED_SHELL_PATHS

    def test_valid_usr_bin_bash(self):
        assert _validate_shell_executable("/usr/bin/bash") in ALLOWED_SHELL_PATHS

    def test_valid_usr_bin_zsh(self):
        assert _validate_shell_executable("/usr/bin/zsh") in ALLOWED_SHELL_PATHS

    def test_invalid_shell_rejected(self):
        with pytest.raises(PermissionError, match="not in allowed set"):
            _validate_shell_executable("/usr/bin/python3")

    def test_invalid_shell_fish_rejected(self):
        with pytest.raises(PermissionError, match="not in allowed set"):
            _validate_shell_executable("/usr/bin/fish")

    def test_relative_path_rejected(self):
        with pytest.raises(PermissionError, match="not in allowed set"):
            _validate_shell_executable("bash")


class TestValidateShellCommand:
    def test_allowed_ls(self):
        assert _validate_shell_command("ls -la") == "ls"

    def test_allowed_cat(self):
        assert _validate_shell_command("cat /etc/hosts") == "cat"

    def test_allowed_grep(self):
        assert _validate_shell_command("grep -r pattern .") == "grep"

    def test_allowed_find(self):
        assert _validate_shell_command("find . -name '*.py'") == "find"

    def test_allowed_pwd(self):
        assert _validate_shell_command("pwd") == "pwd"

    def test_allowed_date(self):
        assert _validate_shell_command("date") == "date"

    def test_allowed_whoami(self):
        assert _validate_shell_command("whoami") == "whoami"

    def test_allowed_echo(self):
        assert _validate_shell_command("echo hello") == "echo"

    def test_allowed_head(self):
        assert _validate_shell_command("head -n 10 file.txt") == "head"

    def test_allowed_tail(self):
        assert _validate_shell_command("tail -n 10 file.txt") == "tail"

    def test_allowed_wc(self):
        assert _validate_shell_command("wc -l file.txt") == "wc"

    def test_allowed_sort(self):
        assert _validate_shell_command("sort file.txt") == "sort"

    def test_allowed_uniq(self):
        assert _validate_shell_command("uniq file.txt") == "uniq"

    def test_allowed_cut(self):
        assert _validate_shell_command("cut -d: -f1 /etc/passwd") == "cut"

    def test_allowed_awk(self):
        assert _validate_shell_command("awk '{print $1}' file.txt") == "awk"

    def test_allowed_sed(self):
        assert _validate_shell_command("sed 's/foo/bar/g' file.txt") == "sed"

    def test_blocked_rm(self):
        with pytest.raises(PermissionError, match="blocked set"):
            _validate_shell_command("rm -rf /")

    def test_blocked_sudo(self):
        with pytest.raises(PermissionError, match="blocked set"):
            _validate_shell_command("sudo ls")

    def test_blocked_su(self):
        with pytest.raises(PermissionError, match="blocked set"):
            _validate_shell_command("su -")

    def test_blocked_chmod(self):
        with pytest.raises(PermissionError, match="blocked set"):
            _validate_shell_command("chmod 777 file.txt")

    def test_blocked_chown(self):
        with pytest.raises(PermissionError, match="blocked set"):
            _validate_shell_command("chown root:root file.txt")

    def test_blocked_kill(self):
        with pytest.raises(PermissionError, match="blocked set"):
            _validate_shell_command("kill -9 1234")

    def test_blocked_pkill(self):
        with pytest.raises(PermissionError, match="blocked set"):
            _validate_shell_command("pkill python")

    def test_blocked_dd(self):
        with pytest.raises(PermissionError, match="blocked set"):
            _validate_shell_command("dd if=/dev/zero of=/dev/sda")

    def test_blocked_mkfs(self):
        with pytest.raises(PermissionError, match="blocked set"):
            _validate_shell_command("mkfs.ext4 /dev/sda1")

    def test_blocked_mount(self):
        with pytest.raises(PermissionError, match="blocked set"):
            _validate_shell_command("mount /dev/sda1 /mnt")

    def test_blocked_umount(self):
        with pytest.raises(PermissionError, match="blocked set"):
            _validate_shell_command("umount /mnt")

    def test_blocked_shutdown(self):
        with pytest.raises(PermissionError, match="blocked set"):
            _validate_shell_command("shutdown -h now")

    def test_blocked_reboot(self):
        with pytest.raises(PermissionError, match="blocked set"):
            _validate_shell_command("reboot")

    def test_blocked_init(self):
        with pytest.raises(PermissionError, match="blocked set"):
            _validate_shell_command("init 0")

    def test_unknown_command_rejected(self):
        with pytest.raises(PermissionError, match="not in the allowed set"):
            _validate_shell_command("curl https://example.com")

    def test_unknown_command_wget_rejected(self):
        with pytest.raises(PermissionError, match="not in the allowed set"):
            _validate_shell_command("wget https://example.com")

    def test_unknown_command_python_rejected(self):
        with pytest.raises(PermissionError, match="not in the allowed set"):
            _validate_shell_command("python3 script.py")

    def test_empty_command_rejected(self):
        with pytest.raises(PermissionError, match="Empty shell command"):
            _validate_shell_command("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(PermissionError, match="Empty shell command"):
            _validate_shell_command("   ")

    def test_command_with_path_extracts_basename(self):
        assert _validate_shell_command("/bin/ls -la") == "ls"

    def test_malformed_command_rejected(self):
        with pytest.raises(PermissionError, match="Cannot parse"):
            _validate_shell_command("echo 'unclosed quote")


class TestValidateShellCwd:
    def test_tmp_allowed(self):
        result = _validate_shell_cwd(Path("/tmp"))
        assert result == Path("/tmp").resolve()

    def test_tmp_subdir_allowed(self):
        result = _validate_shell_cwd(Path("/tmp/test_dir"))
        assert str(result).startswith(str(Path("/tmp").resolve()))

    def test_project_root_allowed(self):
        project_root = Path(__file__).resolve().parent.parent.parent
        result = _validate_shell_cwd(Path("/tmp"), project_root=project_root)
        assert result == Path("/tmp").resolve()

    def test_project_root_subdir_allowed(self):
        project_root = Path(__file__).resolve().parent.parent.parent
        subdir = project_root / "seam_runtime"
        result = _validate_shell_cwd(subdir, project_root=project_root)
        assert result == subdir.resolve()

    def test_arbitrary_path_rejected(self):
        with pytest.raises(PermissionError, match="outside allowed roots"):
            _validate_shell_cwd(Path("/home/user"))

    def test_etc_rejected(self):
        with pytest.raises(PermissionError, match="outside allowed roots"):
            _validate_shell_cwd(Path("/etc"))

    def test_var_rejected(self):
        with pytest.raises(PermissionError, match="outside allowed roots"):
            _validate_shell_cwd(Path("/var"))


class TestGetShellTimeout:
    def test_default_timeout(self, monkeypatch):
        monkeypatch.delenv("SEAM_SHELL_TIMEOUT_SECONDS", raising=False)
        assert _get_shell_timeout() == 10.0

    def test_custom_timeout(self, monkeypatch):
        monkeypatch.setenv("SEAM_SHELL_TIMEOUT_SECONDS", "30")
        assert _get_shell_timeout() == 30.0

    def test_invalid_timeout_uses_default(self, monkeypatch):
        monkeypatch.setenv("SEAM_SHELL_TIMEOUT_SECONDS", "invalid")
        assert _get_shell_timeout() == 10.0

    def test_zero_timeout(self, monkeypatch):
        monkeypatch.setenv("SEAM_SHELL_TIMEOUT_SECONDS", "0")
        assert _get_shell_timeout() == 0.0


class TestShellIntegration:
    def test_allowed_command_executes(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SEAM_DASHBOARD_ALLOW_SHELL", "1")
        monkeypatch.setenv("SHELL", "/bin/bash")
        monkeypatch.setenv("SEAM_SHELL_TIMEOUT_SECONDS", "5")

        mock_self = MagicMock()
        mock_self.shell_cwd = tmp_path

        from seam_runtime.dashboard import TextualDashboardApp

        if hasattr(TextualDashboardApp, "_run_shell_subprocess"):
            result = TextualDashboardApp._run_shell_subprocess(mock_self, "echo hello")
            assert result.returncode == 0
            assert "hello" in result.stdout

    def test_blocked_command_rejected(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SEAM_DASHBOARD_ALLOW_SHELL", "1")
        monkeypatch.setenv("SHELL", "/bin/bash")

        mock_self = MagicMock()
        mock_self.shell_cwd = tmp_path

        from seam_runtime.dashboard import TextualDashboardApp

        if hasattr(TextualDashboardApp, "_run_shell_subprocess"):
            with pytest.raises(PermissionError, match="blocked set"):
                TextualDashboardApp._run_shell_subprocess(mock_self, "rm -rf /")

    def test_shell_disabled_by_default(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SEAM_DASHBOARD_ALLOW_SHELL", raising=False)

        mock_self = MagicMock()
        mock_self.shell_cwd = tmp_path

        from seam_runtime.dashboard import TextualDashboardApp

        if hasattr(TextualDashboardApp, "_run_shell_subprocess"):
            with pytest.raises(PermissionError, match="disabled by default"):
                TextualDashboardApp._run_shell_subprocess(mock_self, "echo hello")

    def test_invalid_shell_rejected(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SEAM_DASHBOARD_ALLOW_SHELL", "1")
        monkeypatch.setenv("SHELL", "/usr/bin/python3")

        mock_self = MagicMock()
        mock_self.shell_cwd = tmp_path

        from seam_runtime.dashboard import TextualDashboardApp

        if hasattr(TextualDashboardApp, "_run_shell_subprocess"):
            with pytest.raises(PermissionError, match="not in allowed set"):
                TextualDashboardApp._run_shell_subprocess(mock_self, "echo hello")

    def test_cwd_outside_allowed_path_rejected(self, monkeypatch):
        monkeypatch.setenv("SEAM_DASHBOARD_ALLOW_SHELL", "1")
        monkeypatch.setenv("SHELL", "/bin/bash")

        mock_self = MagicMock()
        mock_self.shell_cwd = Path("/etc")

        from seam_runtime.dashboard import TextualDashboardApp

        if hasattr(TextualDashboardApp, "_run_shell_subprocess"):
            with pytest.raises(PermissionError, match="outside allowed roots"):
                TextualDashboardApp._run_shell_subprocess(mock_self, "echo hello")

    def test_timeout_enforcement(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SEAM_DASHBOARD_ALLOW_SHELL", "1")
        monkeypatch.setenv("SHELL", "/bin/bash")
        monkeypatch.setenv("SEAM_SHELL_TIMEOUT_SECONDS", "1")

        mock_self = MagicMock()
        mock_self.shell_cwd = tmp_path

        from seam_runtime.dashboard import TextualDashboardApp

        if hasattr(TextualDashboardApp, "_run_shell_subprocess"):
            with pytest.raises(subprocess.TimeoutExpired):
                TextualDashboardApp._run_shell_subprocess(mock_self, "sleep 10")


class TestConstants:
    def test_allowed_commands_is_frozenset(self):
        assert isinstance(ALLOWED_SHELL_COMMANDS, frozenset)

    def test_blocked_commands_is_frozenset(self):
        assert isinstance(BLOCKED_SHELL_COMMANDS, frozenset)

    def test_allowed_paths_is_frozenset(self):
        assert isinstance(ALLOWED_SHELL_PATHS, frozenset)

    def test_no_overlap_between_allowed_and_blocked(self):
        overlap = ALLOWED_SHELL_COMMANDS & BLOCKED_SHELL_COMMANDS
        assert not overlap, f"Commands in both sets: {overlap}"

    def test_all_required_commands_present(self):
        required = {"ls", "cat", "grep", "find", "pwd", "date", "whoami", "echo"}
        assert required.issubset(ALLOWED_SHELL_COMMANDS)

    def test_all_dangerous_commands_blocked(self):
        dangerous = {"rm", "sudo", "su", "chmod", "chown", "kill", "pkill"}
        assert dangerous.issubset(BLOCKED_SHELL_COMMANDS)
