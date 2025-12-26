import sys
import os
import json
import hashlib

def calc_md5(file_path, chunk_size=1024 * 1024):
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            md5.update(chunk)
    return md5.hexdigest()

def main():
    if len(sys.argv) < 2:
        print("请将一个或多个 .pak 文件拖入该脚本运行。")
        return

    result = []

    for file_path in sys.argv[1:]:
        if not os.path.isfile(file_path):
            continue

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        file_hash = calc_md5(file_path)

        item = {
            "name": file_name,
            "hash": file_hash,
            "base": "",
            "diff": "",
            "sizeInBytes": file_size,
            "bPrimary": 0
        }

        result.append(item)

    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
