"""
Beta version of a  wrapper using PTY to execute Codebuff commands.
"""

import os
import select
from typing import Dict
import asyncio
import ptyprocess
import tempfile
import subprocess
from pathlib import Path

from dump import dump
from tests import run_tests
from utils import get_lite_dataset
import json

def diff_versus_commit(git_dname, commit):
    """
    Take a diff of `git_dname` current contents versus the `commit`.
    """

    diff_cmd = f"git -C {git_dname} diff {commit}"
    diff_output = subprocess.check_output(diff_cmd.split()).decode()
    return diff_output

async def execute_codebuff(instructions: str, options: Dict[str, str]) -> str:
    """Execute a Codebuff command using PTY"""
    output = ""
    shell = "zsh"  # Assuming Unix-like system since PTY is required
    pty = None

    try:
        # Run with NO_COLOR=1 to disable terminal control sequences
        env = dict(os.environ)
        env['NO_COLOR'] = '1'
        
        # Write instructions to file
        instructions_path = os.path.join(options["cwd"], "instructions.md")
        with open(instructions_path, "w") as f:
            f.write(instructions)
            
        pty = ptyprocess.PtyProcess.spawn([shell], env=env, cwd=options["cwd"])
        last_read = asyncio.get_event_loop().time()
        
        print(f"starting codebuff", options["cwd"])
        pty.write(f'codebuff . "please solve the problem specified in instructions.md. don\'t write or run any tests to solve this problem, it should be done in just one-shot."\n'.encode())

        while True:
            current_time = asyncio.get_event_loop().time()
            time_since_last_read = current_time - last_read

            if not pty.isalive():
                break

            # if time_since_last_read > 30: # Increased timeout for git operations
            #     break

            # if time_since_last_read > 10 and "Wait..." not in output and "file:" not in output:
            #     break

            if not select.select([pty.fd], [], [], 1.0)[0]:
                await asyncio.sleep(0)
                continue

            try:
                data = pty.read()
            except (ptyprocess.PtyProcessError):
                break

            if not data:
                continue

            decoded = data.decode()
            output += decoded
            print(decoded, end="", flush=True)
            last_read = current_time

            if "Complete!" in output:
                break

            await asyncio.sleep(0)

    finally:
        print('codebuff to be terminated')
        if pty and pty.isalive():
            pty.terminate()

    print('codebuff terminated')
    return output


def process_one_instance(entry, num_tries=1):
    """Process one instance from SWE Bench using codebuff."""
    instance_id = entry["instance_id"]
    base_commit = entry["base_commit"]

    print("=" * 60)
    dump(instance_id)
    print("=" * 60)
    problem_statement = entry["problem_statement"]
    print(problem_statement)

    with tempfile.TemporaryDirectory(dir="/tmp/mnt/aider") as git_tempdir:
        dump(git_tempdir)
        checkout_repo(git_tempdir, entry)

        options = {
            "cwd": git_tempdir,
        }

        print(f"Running codebuff in {git_tempdir}")
        output = ""
        # output = asyncio.run(execute_codebuff(problem_statement, options))
        print(f"Codebuff output: {output}")

        # Run tests after codebuff makes changes
        # passed, test_output = run_tests(entry, use_test_patch=True)
        model_patch = diff_versus_commit(git_tempdir, entry["base_commit"])
        passed, output = run_tests(
            entry,
            model_patch=model_patch,
            use_test_patch=False,
        )

        if passed:
            print("Tests passed!")
        else:
            print("Tests failed:")
            print(test_output)


def checkout_repo(git_tempdir, entry):
    """
    Clone the SWE Bench entry's git repo into git_tempdir at the base_commit.
    """
    github_url = "https://github.com/"
    repo_url = github_url + entry["repo"]
    commit = entry["base_commit"]

    print(repo_url, commit)

    cmd = f"git clone {repo_url} {git_tempdir}"
    subprocess.run(cmd.split(), check=True)

    cmd = f"git -c advice.detachedHead=false -C {git_tempdir} checkout {commit}"
    subprocess.run(cmd.split(), check=True)


def main():
    """Process SWE Bench dataset using codebuff."""
    dataset = get_lite_dataset()
    for instance_id, entry in dataset.items():
        try:
            process_one_instance(entry)
        except Exception as e:
            print(f"Error processing {instance_id}: {e}")


if __name__ == "__main__":
    main()