"""
Harness using PTY to execute Codebuff commands for SWE Bench. 
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
from pathlib import Path
import os
from prompts import CODEBUFF_INSTRUCTION, CODEBUFF_PLANNING_INSTRUCTION

# Create temp directory for codebuff operations
os.makedirs("/tmp/mnt/codebuff", exist_ok=True)

PREDS_DNAME = Path("predictions")
REPOS_DNAME = Path("repos")

# Global args variable to store command line arguments
args = None

def diff_versus_commit(git_dname, commit):
    """
    Take a diff of `git_dname` current contents versus the `commit`.
    """

    diff_cmd = f"git -C {git_dname} diff {commit}"
    diff_output = subprocess.check_output(diff_cmd.split()).decode()
    return diff_output

async def execute_codebuff(instructions: str, options: Dict[str, str], prompt: str) -> str:
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
        pty.write(f'codebuff . "{prompt}"\n'.encode())

        dir_name = options["cwd"].split('/')[-1]
        while True:
            current_time = asyncio.get_event_loop().time()
            time_since_last_read = current_time - last_read

            if not pty.isalive():
                break

            if time_since_last_read > 30 and f'{dir_name} >' in decoded:
                break

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
        if pty and pty.isalive():
            pty.terminate()

    return output

def process_one_instance(entry, num_tries=1, model_name_or_path="codebuff", run_id=None):
    """Process one instance from SWE Bench using codebuff."""
    instance_id = entry["instance_id"]
    base_commit = entry["base_commit"]

    # Use run_id subdirectory if specified
    out_dname = PREDS_DNAME / model_name_or_path
    if run_id:
        out_dname = out_dname / run_id
    out_fname = out_dname / (instance_id + ".json")
    if out_fname.exists():
        print(f"Skipping {instance_id} because prediction already exists")
        return

    print("=" * 60)
    dump(instance_id)
    print("=" * 60)
    problem_statement = entry["problem_statement"]
    print(problem_statement)

    with tempfile.TemporaryDirectory(dir="/tmp/mnt/codebuff") as git_tempdir:
        dump(git_tempdir)
        checkout_repo(git_tempdir, entry)

        options = {
            "cwd": git_tempdir,
        }

        print(f"Running codebuff planning in {git_tempdir}")
        if args.dry_run:
            output = "dry run, this is not actually calling Codebuff"
        else:
            # First run planning step
            output = asyncio.run(execute_codebuff(problem_statement, options, CODEBUFF_PLANNING_INSTRUCTION))
            print(f"Codebuff planning finished")
            
            # Then run implementation step
            print(f"Running codebuff implementation in {git_tempdir}")
            output = asyncio.run(execute_codebuff(problem_statement, options, CODEBUFF_INSTRUCTION))
            
            print(f"Codebuff implementation finished")

        # Run tests after codebuff makes changes
        # passed, test_output = run_tests(entry, use_test_patch=True)
        model_patch = diff_versus_commit(git_tempdir, entry["base_commit"])
        passed, test_output = run_tests(
            entry,
            model_patch=model_patch,
            use_test_patch=False,
        )
            
        # Record the results for the logs
        result = dict(
            # Required args for running eval tests
            instance_id=instance_id,
            model_name_or_path=model_name_or_path,
            model_patch=model_patch,
            # For computing stats
            cost=0,  # Codebuff doesn't track costs this way
            edit_outcome=True,  # Codebuff always attempts edits
            lint_outcome=True,  # No linting in Codebuff
            test_outcome=passed
        )
        
        # Save prediction to JSON file
        out_dname.mkdir(exist_ok=True, parents=True)
        out_fname.write_text(json.dumps(result, indent=4))
                
        # # We were UNABLE to run tests
        # if passed is None:
        #     print("Tests failed to run")
        #     return

        # if passed:
        #     print("Tests passed (but they were expected to)")
        #     return


def checkout_repo(git_tempdir, entry):
    """
    Clone the SWE Bench entry's git repo into git_tempdir at the base_commit.
    Make a tempdir if no git_tempdir provided.
    """
    github_url = "https://github.com/"
    repo_url = github_url + entry["repo"]
    commit = entry["base_commit"]

    print(repo_url, commit)

    # Extract repo name from URL
    repo_name = repo_url.split("/")[-1].split(".")[0]
    repo_name += ".git"

    # Create repos directory if needed
    REPOS_DNAME.mkdir(exist_ok=True)
    bare_repo = REPOS_DNAME / repo_name

    if not bare_repo.exists():
        cmd = f"git clone --bare {repo_url} {bare_repo}"
        subprocess.run(cmd.split(), check=True)

    cmd = f"git clone {bare_repo} {git_tempdir}"
    subprocess.run(cmd.split(), check=True)

    cmd = f"git -c advice.detachedHead=false -C {git_tempdir} checkout {commit}"
    subprocess.run(cmd.split(), check=True)


def main():
    """Process SWE Bench dataset using codebuff."""
    import argparse
    from datetime import datetime
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Skip actual codebuff execution')
    parser.add_argument('--model-name', default='codebuff', help='Model name for predictions folder')
    parser.add_argument('--run-id', help='Run ID for organizing outputs (default: current timestamp)')
    global args
    args = parser.parse_args()
    
    # Generate timestamp-based run ID if not specified
    run_id = args.run_id
    if not run_id:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    dataset = get_lite_dataset()
    for instance_id, entry in dataset.items():
        try:
            process_one_instance(entry, model_name_or_path=args.model_name, run_id=run_id)
        except Exception as e:
            print(f"Error processing {instance_id}: {e}")


if __name__ == "__main__":
    main()