#!/usr/bin/env python3
"""
TokenGuard 🦞 — 本地日志拦截器 (v4 — 红队三轮审计加固版)
==========================================================
用途：拦截长日志输出，静默写入本地文件，仅向终端打印退出码和最后 N 行摘要。
安全声明：本脚本 100% 透明，不含任何网络请求、base64 解码或动态 eval() 操作。
仅使用 Python 内置库 (sys, subprocess, os, re, unicodedata, uuid, shutil)。

v4 变更 (红队第三轮审计修补)：
  - 修复 tail_log() 净化调用退化（v3 回归 Bug）
  - query_log() 输出前二次净化
  - 命令黑名单增加软链接解析（shutil.which + os.path.realpath）
  - --query 关键词长度/字符集校验，防信息泄露
"""

import sys
import os
import re
import subprocess
import unicodedata
import uuid
import shutil

# ─── 配置常量 ───────────────────────────────────────────────────────────
LOG_DIR = ".claw_logs"
LOG_FILE = os.path.join(LOG_DIR, "step.log")          # 净化版日志
RAW_LOG_FILE = os.path.join(LOG_DIR, "step.raw.log")   # 原文日志（仅人工审阅）
TAIL_LINES = 30  # 打印日志的最后 N 行（30 行足够覆盖大多数构建错误，Agent 需更多时用 --query）
LOG_SIZE_LIMIT = 50 * 1024 * 1024  # 50MB，超过此大小拒绝读入内存
# ────────────────────────────────────────────────────────────────────────

# ─── 命令黑名单 ────────────────────────────────────────────────────────
# 这些命令存在数据泄露或远程执行风险，禁止通过 TokenGuard 包装执行。
BLOCKED_COMMANDS = {
    "curl", "wget", "nc", "netcat", "ncat",
    "ssh", "scp", "rsync", "sftp",
    "telnet", "ftp",
    "python", "python3", "node", "ruby", "perl",  # 防止嵌套脚本执行
    "sh", "bash", "zsh", "dash",                    # Shell 包装器
    "fish", "csh", "tcsh", "ksh",                    # 小众 Shell
    "env", "sudo", "su", "npx", "pnpx", "bunx",     # 权限提升 / 包装执行
    "nohup", "time", "watch", "xargs", "doas",       # 执行包装器
}
# ────────────────────────────────────────────────────────────────────────

# ─── 零宽字符列表 ──────────────────────────────────────────────────────
ZERO_WIDTH_CHARS = [
    "\u200b",  # Zero Width Space
    "\u200c",  # Zero Width Non-Joiner
    "\u200d",  # Zero Width Joiner
    "\ufeff",  # BOM / Zero Width No-Break Space
    "\u2060",  # Word Joiner
    "\u200e",  # Left-to-Right Mark
    "\u200f",  # Right-to-Left Mark
    "\u00ad",  # Soft Hyphen
    "\u034f",  # Combining Grapheme Joiner
    "\u2028",  # Line Separator
    "\u2029",  # Paragraph Separator
]
# ────────────────────────────────────────────────────────────────────────

# ─── 提示词注入检测模式 ────────────────────────────────────────────────
INJECTION_PATTERNS = [
    # 英文注入关键词
    r'(?i)(ignore|forget|override|disregard)\s+(all\s+)?(previous|above|prior|system)\s+(instructions?|prompts?|rules?|constraints?)',
    r'(?i)new\s+(system\s+)?(instruction|directive|prompt|role)',
    r'(?i)you\s+are\s+now\s+(a|an|the)',
    r'(?i)act\s+as\s+(a|an|if)',
    r'(?i)system\s*(prompt|override|message)',
    # 中文注入关键词
    r'(?i)(忽略|覆盖|遗忘|绕过|无视).{0,6}(指令|约束|规则|提示词|安全)',
    r'新(的)?(系统)?(指令|角色|身份|任务)',
    # 危险命令模式
    r'(?i)rm\s+-r?f\s+[~/\*]',
    r'(?i)(curl|wget|fetch)\s+https?://',
    r'(?i)requests?\.(get|post|put|delete)\s*\(',
    r'(?i)(eval|exec)\s*\(',
    r'(?i)(ssh|api[_\-]?key|token|secret|password)\s*[:=]',
    # LLM 特殊 token 格式
    r'\[INST\]|\[/INST\]',
    r'<\|?(system|user|assistant|im_start|im_end)\|?>',
    r'<<\s*SYS\s*>>',
]

_COMPILED_PATTERNS = [re.compile(p) for p in INJECTION_PATTERNS]
# ────────────────────────────────────────────────────────────────────────


def ensure_log_dir():
    """确保日志目录存在。"""
    if not os.path.isdir(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)


def normalize_line(line):
    """
    Unicode 正规化预处理：
    1. NFKC 正规化 — 将全角字母、兼容字符还原为标准形式
    2. 过滤零宽字符 — 移除可用于隐匿注入的不可见字符
    """
    normalized = unicodedata.normalize("NFKC", line)
    for zw in ZERO_WIDTH_CHARS:
        normalized = normalized.replace(zw, " ")
    # 压缩连续空格为单个空格
    normalized = re.sub(r' {2,}', ' ', normalized)
    return normalized


def sanitize_log_line(line):
    """
    检查单行日志是否包含提示词注入特征。
    先做 Unicode 正规化，再匹配注入模式。
    返回净化后的行（安全行原样返回，恶意行替换为占位符）。
    """
    normalized = normalize_line(line)
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(normalized):
            return "[TG:BLOCKED]\n"
    return line


def validate_command(cmd_args):
    """
    命令黑名单校验。
    拒绝执行存在数据泄露或远程执行风险的命令。
    同时解析软链接，防止通过 ln -s 别名绕过。
    """
    if not cmd_args:
        return
    base_cmd = os.path.basename(cmd_args[0]).lower()

    # 检查1：直接名称匹配
    if base_cmd in BLOCKED_COMMANDS:
        print(f"[TokenGuard] ⛔ 拒绝: {base_cmd}")
        print("[TokenGuard] 如确需执行，请直接在终端运行（不经过 TokenGuard）。")
        sys.exit(2)

    # 检查2：解析软链接，获取真实可执行文件名
    resolved_path = shutil.which(cmd_args[0])
    if resolved_path:
        real_path = os.path.realpath(resolved_path)
        real_base = os.path.basename(real_path).lower()
        if real_base in BLOCKED_COMMANDS:
            print(f"[TokenGuard] ⛔ 拒绝: {base_cmd} (软链接→{real_base})")
            print("[TokenGuard] 如确需执行，请直接在终端运行（不经过 TokenGuard）。")
            sys.exit(2)


def run_command(cmd_args):
    """
    在子进程中执行命令。
    双写模式：
      - step.raw.log: 完整原文（仅供人工审阅，Agent 禁止直接读取）
      - step.log:     净化版（Agent 可安全读取）
    返回子进程的退出码。
    """
    ensure_log_dir()

    with open(RAW_LOG_FILE, "w", encoding="utf-8", errors="replace") as raw_f, \
         open(LOG_FILE, "w", encoding="utf-8", errors="replace") as safe_f:

        cmd_str = " ".join(cmd_args)
        raw_f.write(f"[TokenGuard] Command: {cmd_str}\n")
        raw_f.write("=" * 60 + "\n")
        safe_f.write(f"[TokenGuard] Command: {sanitize_log_line(cmd_str).rstrip()}\n")
        safe_f.write("=" * 60 + "\n")
        raw_f.flush()
        safe_f.flush()

        process = subprocess.Popen(
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        for line in process.stdout:
            try:
                decoded = line.decode("utf-8", errors="replace")
            except Exception:
                decoded = str(line)
            # 双写：原文写入 raw，净化版写入 safe
            raw_f.write(decoded)
            raw_f.flush()
            safe_f.write(sanitize_log_line(decoded))
            safe_f.flush()

        process.wait()

    return process.returncode


def tail_log(n=TAIL_LINES):
    """
    读取净化版日志的最后 n 行。
    使用 UUID 单行标记，防止日志内容伪造区域边界。
    """
    if not os.path.isfile(LOG_FILE):
        return "[TokenGuard] 日志文件不存在。"

    # OOM 熔断：拒绝读取超大日志
    file_size = os.path.getsize(LOG_FILE)
    if file_size > LOG_SIZE_LIMIT:
        return f"[TokenGuard] ⛔ 日志过大（{file_size//1024//1024}MB），请人工查看：tail -n 100 {LOG_FILE}"

    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    total = len(lines)
    tail = lines[-n:] if total > n else lines

    zone_id = uuid.uuid4().hex[:8].upper()
    header = f"# [TG:UNTRUSTED-START:{zone_id}] 日志共{total}行，最后{min(n,total)}行↓\n"
    footer = f"# [TG:UNTRUSTED-END:{zone_id}]\n"

    # step.log 已在写入时净化，此处不再二次过滤
    return header + "".join(tail) + footer


def query_log(keyword=None, line_range=None):
    """
    受控日志查询接口（替代直接 cat step.log）。
    支持关键词搜索和行号范围查询，所有输出均经过净化层。
    """
    if not os.path.isfile(LOG_FILE):
        print("[TokenGuard] 日志文件不存在。")
        return

    # OOM 熔断
    file_size = os.path.getsize(LOG_FILE)
    if file_size > LOG_SIZE_LIMIT:
        print(f"[TokenGuard] ⛔ 日志过大（{file_size//1024//1024}MB），请人工查看：tail -n 100 {LOG_FILE}")
        return

    if not keyword and not line_range:
        # 无参数模式：仅统计行数，不读全文，不生成 zone_id
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            total = sum(1 for _ in f)
        print(f"[TokenGuard] 日志总计 {total} 行。使用 --query <keyword|start-end> 查询。")
        return

    zone_id = uuid.uuid4().hex[:8].upper()

    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    total = len(lines)
    print(f"# [TG:UNTRUSTED-START:{zone_id}]")

    if keyword:
        matches = []
        for i, line in enumerate(lines, 1):
            if keyword.lower() in line.lower():
                matches.append((i, line))
        print(f"[TokenGuard] 搜索 \"{keyword}\"，共 {len(matches)} 处匹配（日志总计 {total} 行）：")
        for line_num, line in matches[:30]:
            safe_line = sanitize_log_line(line.rstrip())
            print(f"  L{line_num}: {safe_line.rstrip()}")
        if len(matches) > 30:
            print(f"  ... 还有 {len(matches) - 30} 条未显示")

    elif line_range:
        start, end = line_range
        start = max(1, start)
        end = min(total, end)
        if end - start > 100:
            end = start + 100
            print(f"[TokenGuard] ⚠️ 单次查询上限 100 行，已截断至 L{start}-L{end}")
        print(f"[TokenGuard] 显示 L{start}-L{end}（日志总计 {total} 行）：")
        for i in range(start - 1, end):
            safe_line = sanitize_log_line(lines[i].rstrip())
            print(f"  L{i+1}: {safe_line.rstrip()}")

    print(f"# [TG:UNTRUSTED-END:{zone_id}]")


def main():
    # ─── --query 受控查询模式 ─────────────────────────────────────
    if len(sys.argv) >= 2 and sys.argv[1] == "--query":
        if len(sys.argv) >= 3:
            arg = sys.argv[2]
            # 尝试解析为行号范围 "10-50"
            range_match = re.match(r'^(\d+)-(\d+)$', arg)
            if range_match:
                query_log(line_range=(int(range_match.group(1)), int(range_match.group(2))))
            else:
                # 关键词校验：限制长度和字符集，防止信息泄露
                if len(arg) > 100:
                    print("[TokenGuard] ⛔ 查询关键词过长（上限 100 字符），已拒绝。")
                    sys.exit(2)
                if not re.match(r'^[\w\s\.\-\:@/\\\[\]\(\)\{\}#=+,;!?*&^%$"\',]+$', arg):
                    print("[TokenGuard] ⛔ 查询关键词包含非法字符，已拒绝。")
                    sys.exit(2)
                query_log(keyword=arg)
        else:
            query_log()
        sys.exit(0)

    # ─── 参数校验 ────────────────────────────────────────────────────
    if len(sys.argv) < 2:
        print("用法:")
        print("  执行命令:  python token_guard.py <command> [args...]")
        print("  查询日志:  python token_guard.py --query <keyword|start-end>")
        print("")
        print("示例:")
        print("  python token_guard.py npm install")
        print("  python token_guard.py --query error")
        print("  python token_guard.py --query 10-50")
        sys.exit(1)

    cmd_args = sys.argv[1:]

    # ─── 命令黑名单校验 ──────────────────────────────────────────────
    validate_command(cmd_args)

    # ─── 执行命令 ────────────────────────────────────────────────────
    print(f"[TokenGuard] 🦞 正在静默执行: {' '.join(cmd_args)}")
    print(f"[TokenGuard] 净化日志: {os.path.abspath(LOG_FILE)}")
    print(f"[TokenGuard] 原文日志: {os.path.abspath(RAW_LOG_FILE)} (仅供人工审阅)")
    print("-" * 60)

    exit_code = run_command(cmd_args)

    # ─── 输出摘要 ────────────────────────────────────────────────────
    print("=" * 60)
    print(f"[TokenGuard] ✅ Exit Code: {exit_code}")
    print("=" * 60)
    print(tail_log(TAIL_LINES))
    print("=" * 60)
    print(f"[TokenGuard] 📄 净化日志: {os.path.abspath(LOG_FILE)}")
    print(f"[TokenGuard] 📄 原文日志: {os.path.abspath(RAW_LOG_FILE)} (⚠️ Agent 禁止直接读取)")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
