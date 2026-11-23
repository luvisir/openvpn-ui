import os
import subprocess
import sys
from pathlib import Path


def test_enable_only_removes_selected_managed_remote_ccd_and_can_retry(tmp_path):
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    binaries = tmp_path / "bin"
    for directory in [local, remote, binaries]:
        directory.mkdir()
    managed = "# managed-by openvpn-ui\ndisable\n"
    (local / "alice").write_text(managed)
    (remote / "alice").write_text(managed)
    (remote / "bob").write_text("custom configuration\n")
    ssh = binaries / "ssh"
    ssh.write_text(f"#!{sys.executable}\n" + "import os,shlex,subprocess,sys\nargs=shlex.split(sys.argv[-1])\nargs[3]=os.environ['TEST_REMOTE']\nsys.exit(subprocess.run(args,input=sys.stdin.buffer.read()).returncode)\n")
    rsync = binaries / "rsync"
    rsync.write_text(f"#!{sys.executable}\n" + "import sys\nassert '--delete' not in sys.argv\n")
    ssh.chmod(0o755)
    rsync.chmod(0o755)
    env = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ["PATH"], TEST_REMOTE=str(remote))
    command = ["bash", "scripts/ui-enable-user.sh", "alice", str(local), "test.invalid"]
    assert subprocess.run(command, env=env, capture_output=True).returncode == 0
    assert not (remote / "alice").exists()
    assert (remote / "bob").read_text() == "custom configuration\n"
    (remote / "alice").write_text(managed)
    assert subprocess.run(command, env=env, capture_output=True).returncode == 0
    assert not (remote / "alice").exists()
    (remote / "alice").write_text("unmanaged\n")
    assert subprocess.run(command, env=env, capture_output=True).returncode != 0
    assert (remote / "alice").read_text() == "unmanaged\n"
