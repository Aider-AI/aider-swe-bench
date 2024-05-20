from swebench_docker.utils import get_test_directives
NOOP_PATCH = (
    "diff --git a/empty.file.{nonce}.ignore b/empty.file.{nonce}.ignore\n"
    "new file mode 100644\n"
    "index 0000000..e69de29\n"
)
def run_tests(entry, model_patch=None, use_new_tests=False, 
              model_name_or_path="none"):
    asyncio.run(run_docker_evaluation(entry_instance, namespace, log_dir, 
                                      timeout, log_suffix))
    log_lines = [line for line in log_lines if line.startswith(">>>>")]