import argparse
import hashlib
import json
import os
import pathlib
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE_URL = os.environ.get("DAT_TRAINING_API_BASE_URL", "https://api.thatcompany.ai/v1").rstrip("/")
TOKEN_ENV_NAMES = ("DAT_TEMP_KEY", "DAT_API_KEY", "THAT_API_KEY", "DAT_SESSION_KEY")
SKIP_NAMES = {".DS_Store", ".git", "__pycache__", ".venv", "venv", "node_modules", "dist", "build"}
SKIP_SUFFIXES = (".pyc", ".pyo")


def die(message, code=2):
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def token_from_env():
    for name in TOKEN_ENV_NAMES:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def read_text_arg(value, file_value, label):
    if value and file_value:
        die(f"use either --{label} or --{label}-file, not both")
    if file_value:
        return pathlib.Path(file_value).read_text()
    if value:
        return value
    die(f"--{label} is required")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def should_skip(path):
    parts = path.parts
    if any(part in SKIP_NAMES for part in parts):
        return True
    if any(part.startswith("._") for part in parts):
        return True
    return path.name.endswith(SKIP_SUFFIXES)


def package_files(root):
    root = root.resolve()
    if not root.is_dir():
        die(f"package path is not a directory: {root}")
    files = []
    for current, dirnames, filenames in os.walk(root):
        current_path = pathlib.Path(current)
        rel_dir = current_path.relative_to(root)
        dirnames[:] = [name for name in dirnames if not should_skip(rel_dir / name)]
        for filename in filenames:
            file_path = current_path / filename
            rel_path = file_path.relative_to(root)
            if should_skip(rel_path):
                continue
            if file_path.is_symlink():
                die(f"symlink is not supported in training artifact: {rel_path.as_posix()}")
            if not file_path.is_file():
                die(f"unsupported non-file entry in training artifact: {rel_path.as_posix()}")
            files.append((file_path, rel_path.as_posix()))
    if not files:
        die("package contains no files")
    return sorted(files, key=lambda item: item[1])


def write_archive(package_dir, output):
    package_dir = pathlib.Path(package_dir)
    output = pathlib.Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for file_path, arcname in package_files(package_dir):
            archive.add(file_path, arcname=arcname, recursive=False)
    return output


def base_url(value):
    return value.rstrip("/")


def api_url(base, path):
    return f"{base_url(base)}/{path.lstrip('/')}"


def json_request(method, url, token=None, body=None):
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        text = error.read().decode("utf-8", errors="replace")
        die(f"{method} {url} failed with HTTP {error.code}: {text[:4000]}")
    except urllib.error.URLError as error:
        die(f"{method} {url} failed: {error}")
    if not payload:
        return {}
    try:
        return json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError:
        die(f"{method} {url} returned non-JSON response")


def download_request(url, output, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read()
    except urllib.error.HTTPError as error:
        text = error.read().decode("utf-8", errors="replace")
        die(f"GET {url} failed with HTTP {error.code}: {text[:4000]}")
    except urllib.error.URLError as error:
        die(f"GET {url} failed: {error}")
    output = pathlib.Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return output


def multipart_body(fields, file_field, file_path, content_type):
    boundary = f"dat-skill-{hashlib.sha256(os.urandom(24)).hexdigest()}"
    chunks = []
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            str(value).encode(),
            b"\r\n",
        ])
    file_name = pathlib.Path(file_path).name
    chunks.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="{file_field}"; filename="{file_name}"\r\n'.encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        pathlib.Path(file_path).read_bytes(),
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def multipart_request(url, fields, file_path, token=None):
    body, content_type = multipart_body(fields, "artifact", file_path, fields["artifactContentType"])
    headers = {"Accept": "application/json", "Content-Type": content_type}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        text = error.read().decode("utf-8", errors="replace")
        die(f"POST {url} failed with HTTP {error.code}: {text[:4000]}")
    except urllib.error.URLError as error:
        die(f"POST {url} failed: {error}")
    try:
        return json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError:
        die(f"POST {url} returned non-JSON response")


def print_json(value):
    print(json.dumps(value, indent=2, sort_keys=True))


def command_pack(args):
    output = write_archive(args.package_dir, args.output)
    print_json({
        "path": str(output),
        "sizeBytes": output.stat().st_size,
        "sha256": sha256_file(output),
    })


def command_submit(args):
    instruction = read_text_arg(args.instruction, args.instruction_file, "instruction")
    token = args.token or (token_from_env() if args.use_env_token else None)
    source = pathlib.Path(args.source)
    with tempfile.TemporaryDirectory() as temp_dir:
        if source.is_dir():
            archive_path = pathlib.Path(args.archive or pathlib.Path(temp_dir) / "artifact.tar.gz")
            write_archive(source, archive_path)
        elif source.is_file():
            archive_path = source
        else:
            die(f"source path does not exist: {source}")
        artifact_name = args.artifact_name or archive_path.name
        fields = {
            "title": args.title,
            "instruction": instruction,
            "artifactName": artifact_name,
            "artifactContentType": args.artifact_content_type,
            "artifactSizeBytes": str(archive_path.stat().st_size),
            "artifactSha256": sha256_file(archive_path),
        }
        response = multipart_request(api_url(args.base_url, "/training/jobs:upload"), fields, archive_path, token)
        print_json(response)


def command_status(args):
    url = args.url or api_url(args.base_url, f"/training/jobs/{args.job_id}")
    token = args.token if args.token else (None if args.url else token_from_env())
    print_json(json_request("GET", url, token=token))


def command_artifacts(args):
    url = api_url(args.base_url, f"/training/jobs/{args.job_id}/artifacts")
    print_json(json_request("GET", url, token=args.token or token_from_env()))


def command_download(args):
    url = api_url(args.base_url, f"/training/jobs/{args.job_id}/artifacts/{args.artifact_id}/content")
    output = download_request(url, args.output, token=args.token or token_from_env())
    print_json({
        "path": str(output),
        "sizeBytes": output.stat().st_size,
        "sha256": sha256_file(output),
    })


def command_cancel(args):
    url = api_url(args.base_url, f"/training/jobs/{args.job_id}/cancel")
    print_json(json_request("POST", url, token=args.token or token_from_env(), body={}))


def build_parser():
    parser = argparse.ArgumentParser(prog="dat_training.py", description="Package, submit, track, and download Dat training jobs.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    pack = subcommands.add_parser("pack", help="Create a Dat training artifact tar.gz")
    pack.add_argument("package_dir")
    pack.add_argument("--output", required=True)
    pack.set_defaults(func=command_pack)

    submit = subcommands.add_parser("submit", help="Upload an artifact and create a training job")
    submit.add_argument("source")
    submit.add_argument("--title", required=True)
    submit.add_argument("--instruction")
    submit.add_argument("--instruction-file")
    submit.add_argument("--base-url", default=DEFAULT_BASE_URL)
    submit.add_argument("--token")
    submit.add_argument("--use-env-token", action="store_true")
    submit.add_argument("--archive")
    submit.add_argument("--artifact-name")
    submit.add_argument("--artifact-content-type", default="application/gzip")
    submit.set_defaults(func=command_submit)

    status = subcommands.add_parser("status", help="Fetch training job status")
    status.add_argument("job_id", nargs="?")
    status.add_argument("--url")
    status.add_argument("--base-url", default=DEFAULT_BASE_URL)
    status.add_argument("--token")
    status.set_defaults(func=command_status)

    artifacts = subcommands.add_parser("artifacts", help="List training job artifacts")
    artifacts.add_argument("job_id")
    artifacts.add_argument("--base-url", default=DEFAULT_BASE_URL)
    artifacts.add_argument("--token")
    artifacts.set_defaults(func=command_artifacts)

    download = subcommands.add_parser("download", help="Download one training job artifact")
    download.add_argument("job_id")
    download.add_argument("artifact_id")
    download.add_argument("--output", required=True)
    download.add_argument("--base-url", default=DEFAULT_BASE_URL)
    download.add_argument("--token")
    download.set_defaults(func=command_download)

    cancel = subcommands.add_parser("cancel", help="Cancel a training job")
    cancel.add_argument("job_id")
    cancel.add_argument("--base-url", default=DEFAULT_BASE_URL)
    cancel.add_argument("--token")
    cancel.set_defaults(func=command_cancel)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "status" and not args.job_id and not args.url:
        die("status requires JOB_ID or --url")
    args.func(args)


if __name__ == "__main__":
    main()
