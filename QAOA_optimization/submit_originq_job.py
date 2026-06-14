import argparse
import getpass
import json
import os
from pathlib import Path

from pyqpanda3.intermediate_compiler import convert_qasm_file_to_qprog
from pyqpanda3.qcloud import QCloudOptions, QCloudService


# 本源量子云提交脚本：读取导出的 QASM，转换成 QPanda3 QProg 后提交到云端后端。
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
    # API key 只从环境变量或交互输入读取，避免写进源码、README 或 git 历史。
    if ask_key:
        return getpass.getpass("OriginQ API key: ").strip()
    api_key = os.environ.get("ORIGINQ_API_KEY")
    if not api_key:
        raise RuntimeError("Please set ORIGINQ_API_KEY or pass --ask-key.")
    return api_key


def result_to_dict(result):
    # SDK 的 result 对象不是普通 dict，这里转成 JSON 方便保存和后续比较。
    data = {
        "job_id": result.job_id(),
        "job_status": str(result.job_status()),
        "error_message": result.error_message(),
    }
    try:
        # counts 是真机 shots 的直接测量次数，是报告里最常用的结果。
        data["counts"] = dict(result.get_counts())
    except Exception as exc:
        data["counts_error"] = repr(exc)
    try:
        # probs 是平台根据任务结果给出的概率字段，保留用于排查 bit 顺序。
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
        # 当前 pyqpanda3 版本返回 dict：后端名 -> 是否可用。
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
    # 直接读取 export_hardware_qasm.py 生成的 OpenQASM，避免手工重写门序列。
    qprog = convert_qasm_file_to_qprog(str(qasm_path))

    options = QCloudOptions()
    # mapping/optimization/amend 交给云端处理芯片拓扑、线路优化和读出校正。
    options.set_mapping(True)
    options.set_optimization(True)
    options.set_amend(True)

    backend = service.backend(args.backend)
    job = backend.run(qprog, shots=args.shots, options=options)
    print("submitted job_id:", job.job_id())
    print("status:", job.status())

    # result() 会等待任务完成；若队列较长，这一步可能需要较久。
    result = job.result()
    data = result_to_dict(result)
    print(json.dumps(data, ensure_ascii=False, indent=2))

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("saved:", output_path)


if __name__ == "__main__":
    main()
