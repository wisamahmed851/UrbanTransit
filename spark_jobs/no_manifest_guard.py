"""Run a pipeline job while making it impossible to read the generator's injection manifest.

Usage: python spark_jobs/no_manifest_guard.py spark_jobs/data_quality.py --mode full

How it works: Python's audit hooks (PEP 578) are called for every `open()` (and os-level file
access) in the process. The hook below raises PermissionError - and prints BLOCKED - if the
path points into data_generator/manifests or at any injection_* file. The wrapped script then
runs exactly as it would normally (runpy). If the job finishes, it never opened those files.
(The Spark JVM reads only HDFS paths passed by the Python code, and nothing under
data_generator/ is ever copied to HDFS.)

NestJS analogy: a guard in front of a route - the job only runs behind it.
"""

import runpy
import sys

FORBIDDEN = ("data_generator/manifests", "injection_manifest", "injection_keys")
opened_count = 0
blocked = []


def guard(event: str, args: tuple) -> None:
    global opened_count
    if event in ("open", "os.listdir", "os.scandir") and args:
        path = str(args[0]).replace("\\", "/")
        opened_count += event == "open"
        if any(f in path for f in FORBIDDEN):
            blocked.append(path)
            print(f"BLOCKED: pipeline tried to access {path}", file=sys.stderr, flush=True)
            raise PermissionError(f"no_manifest_guard: access to {path} is not allowed in the pipeline")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: no_manifest_guard.py <script.py> [args...]")
    script = sys.argv[1]
    sys.argv = sys.argv[1:]                      # the wrapped script sees its normal argv
    sys.addaudithook(guard)
    print(f"no_manifest_guard: active for {script} (blocking {', '.join(FORBIDDEN)})", flush=True)
    try:
        runpy.run_path(script, run_name="__main__")
    finally:
        verdict = f"BLOCKED {len(blocked)} manifest access(es)" if blocked else "no manifest access"
        print(f"no_manifest_guard: {opened_count} file opens checked - {verdict}", flush=True)
