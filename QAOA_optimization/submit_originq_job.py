import argparse
import getpass
import json
import os
from pathlib import Path

from pyqpanda3.intermediate_compiler import convert_qasm_file_to_qprog
from pyqpanda3.qcloud import QCloudOptions, QCloudService


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qasm", required=True, help="OpenQASM 2.0 file to submit.")
    parser.add_argument("--backend", default=None, help="Cloud backend name. Omit with --list-backends first.")
    parser.add_argument("--shots", type=int, default=2000)
    parser.add_argument("--output", default=None, help="Where to save hardware counts JSON.")
    parser.add_argument("--list-backends", action="store_true", help="Only list available backends.")
    parser.add_argument("--ask-key", action="store_true", help="Prompt for API key instead of reading ORIGINQ_API_KEY.")
    return parser.parse_args()


def require_api_key(ask_key):
    if ask_key:
        return getpass.getpass("OriginQ API key: ").strip()
    api_key = os.environ.get("ORIGINQ_API_KEY")
    if not api_key:
        raise RuntimeError("Please set ORIGINQ_API_KEY or pass --ask-key.")
    return api_key


def result_to_dict(result):
    data = {
        "job_id": result.job_id(),
        "job_status": str(result.job_status()),
        "error_message": result.error_message(),
    }
    try:
        data["counts"] = dict(result.get_counts())
    except Exception as exc:
        data["counts_error"] = repr(exc)
    try:
        data["probs"] = dict(result.get_probs())
    except Exception as exc:
        data["probs_error"] = repr(exc)
    try:
        data["origin_data"] = result.origin_data()
    except Exception as exc:
        data["origin_data_error"] = repr(exc)
    return data


def main():
    args = parse_args()
    service = QCloudService(api_key=require_api_key(args.ask_key))

    if args.list_backends:
        backends = service.backends()
        if isinstance(backends, dict):
            for name, available in backends.items():
                print("{}\t{}".format(name, available))
        else:
            for backend in backends:
                print(backend)
        return

    if not args.backend:
        raise RuntimeError("Please pass --backend. Use --list-backends to see available names.")

    qasm_path = Path(args.qasm)
    qprog = convert_qasm_file_to_qprog(str(qasm_path))

    options = QCloudOptions()
    options.set_mapping(True)
    options.set_optimization(True)
    options.set_amend(True)

    backend = service.backend(args.backend)
    job = backend.run(qprog, shots=args.shots, options=options)
    print("submitted job_id:", job.job_id())
    print("status:", job.status())

    result = job.result()
    data = result_to_dict(result)
    print(json.dumps(data, ensure_ascii=False, indent=2))

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("saved:", output_path)


if __name__ == "__main__":
    main()
