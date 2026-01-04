#!/usr/bin/env python3
import subprocess
import shutil
import sys
import re
from pathlib import Path

# ===================== 可配置项 =====================

ANDROID_DIR = "/sdcard/AliYunPan/备份文件/来自分享/yitianchenyuqi/."

WORK_DIR = Path("./work")
PULL_DIR = WORK_DIR / "pull"
OUT_DIR = WORK_DIR / "out"

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov"}

FFMPEG_ARGS = [
    "-c:v", "h264_nvenc",
    "-profile:v", "main",
    "-level", "4.0",
    "-preset", "slow",
    "-crf", "20",
    "-c:a", "copy",
    "-movflags", "+faststart",
]

# ===================== 工具函数 =====================

def run(cmd, check=True):
    print("[CMD]", " ".join(cmd))
    subprocess.run(cmd, check=check)

def is_dir_empty(path: Path) -> bool:
    return not any(path.iterdir())

def ask_dir_policy(path: Path) -> str:
    print(f"\n目录 {path} 已存在且不为空：")
    print("  c = 清空后重新 pull")
    print("  k = 保留现有内容（跳过 adb pull）")
    print("  q = 退出脚本")

    while True:
        choice = input("请选择 [c/k/q]: ").strip().lower()
        if choice in {"c", "k", "q"}:
            return choice

def ensure_pull_dir(path: Path) -> bool:
    """
    返回值：
      True  -> 需要执行 adb pull
      False -> 跳过 adb pull，使用已有内容
    """
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return True

    if is_dir_empty(path):
        return True

    choice = ask_dir_policy(path)

    if choice == "c":
        shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
        return True

    if choice == "k":
        print("使用已有 pull 目录内容，跳过 adb pull")
        return False

    print("已退出")
    sys.exit(0)

def ensure_clean_dir(path: Path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)

# ===================== 重命名逻辑 =====================

def rename_video(original_name: str) -> str:
    """
    从文件名中提取“第XX集”，统一命名为“第XX集”
    如果无法识别集数，则保留原名
    """

    name = original_name.strip()

    # 匹配：第1集 / 第01集 / 第 1 集
    m = re.search(r"第\s*(\d+)\s*集", name)
    if not m:
        # 没匹配到，原样返回（防止误伤）
        return name

    ep = int(m.group(1))
    return f"{ep:02d}"

# ===================== 主流程 =====================

def main():
    WORK_DIR.mkdir(exist_ok=True)

    # pull 目录策略（决定是否执行 adb pull）
    need_pull = ensure_pull_dir(PULL_DIR)

    # out 目录始终重建
    ensure_clean_dir(OUT_DIR)

    # 1. pull（如需要）
    if need_pull:
        print("== Pull videos from device ==")
        run(["adb", "pull", ANDROID_DIR, str(PULL_DIR)])
    else:
        print("== Skip adb pull ==")

    pulled_root = PULL_DIR
    if not pulled_root.exists():
        print("未找到 pull 后的视频目录")
        sys.exit(1)

    videos = [p for p in pulled_root.iterdir() if p.suffix.lower() in VIDEO_EXTS]
    if not videos:
        print("未发现视频文件")
        sys.exit(0)

    # 2. 清空设备端原目录
    android_dir = Path(ANDROID_DIR).as_posix()
    run(["adb", "shell", "rm", "-rf", f"{android_dir}/."])

    # 3. 转码 + 重命名
    print("== Transcoding videos ==")
    for src in videos:
        new_name = rename_video(src.stem)
        out_file = OUT_DIR / f"{new_name}.mp4"

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(src),
            *FFMPEG_ARGS,
            str(out_file),
        ]
        run(cmd)

    # 4. push 回设备
    print("== Push back to device ==")
    run(["adb", "push", f"{OUT_DIR}/.", android_dir)

    print("== Done ==")

if __name__ == "__main__":
    main()


