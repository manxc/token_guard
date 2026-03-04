#!/usr/bin/env python3
"""
verify_state.py — state.md 完整性校验器 (v4.1 — 第四轮审计修补)
==========================================================
用途：在 Agent 恢复 Checkpoint 之前，代码层强制校验 state.md 的合法性。
安全声明：本脚本 100% 透明，仅使用 Python 内置库 (sys, os, re, unicodedata)。

v4.1 变更 (第四轮审计修补)：
  - 新增全文跨行模式检测（re.DOTALL），防拆分注入
  - TIME/HASH 结构校验统一使用 normalized_content
  - CHECKPOINT_HASH 增加格式正则校验
  - 成功报告改为动态生成，与实际校验项同步
"""

import sys
import os
import re
import unicodedata

# ─── 零宽字符列表（与 token_guard.py 共享） ────────────────────────────
ZERO_WIDTH_CHARS = [
    "\u200b", "\u200c", "\u200d", "\ufeff", "\u2060",
    "\u200e", "\u200f", "\u00ad", "\u034f", "\u2028", "\u2029",
]

# ─── 允许的章节标题白名单 ───────────────────────────────────────────────
ALLOWED_SECTIONS = {
    "🦞 Checkpoint State",
    "安全签名",
    "已完成任务",
    "当前系统状态",
    "环境变量",
    "下一步计划",
    "关键文件变更",
}

# ─── 危险内容模式 ──────────────────────────────────────────────────────
DANGER_PATTERNS = [
    # 危险命令
    r'(?i)rm\s+-r?f\s+[~/\*]',
    r'(?i)(curl|wget|fetch)\s+https?://',
    r'(?i)(eval|exec)\s*\(',
    r'(?i)(ssh|api[_\-]?key|token|secret|password)\s*[:=]\s*["\']?\S',
    # 提示词注入
    r'(?i)(ignore|forget|override|disregard)\s+(all\s+)?(previous|above|prior|system)\s+(instructions?|prompts?|rules?|constraints?)',
    r'(?i)(忽略|覆盖|遗忘|绕过|无视).{0,6}(指令|约束|规则|提示词|安全)',
    r'(?i)new\s+(system\s+)?(instruction|directive|prompt|role)',
    r'新(的)?(系统)?(指令|角色|身份|任务)',
    r'(?i)system\s*(prompt|override|message)',
    # LLM 特殊 token
    r'\[INST\]|\[/INST\]',
    r'<\|?(system|user|assistant|im_start|im_end)\|?>',
    r'<<\s*SYS\s*>>',
]

_COMPILED_DANGER = [re.compile(p) for p in DANGER_PATTERNS]


def normalize_line(line):
    """
    Unicode 正规化预处理（与 token_guard.py 共享逻辑）：
    1. NFKC 正规化 — 将全角字母、兼容字符还原为标准形式
    2. 零宽字符替换为空格 + 压缩连续空格
    """
    normalized = unicodedata.normalize("NFKC", line)
    for zw in ZERO_WIDTH_CHARS:
        normalized = normalized.replace(zw, " ")
    normalized = re.sub(r' {2,}', ' ', normalized)
    return normalized


def verify_state_md(path="state.md"):
    """
    校验 state.md 的合法性。
    返回 (is_valid: bool, reasons: list[str], check_results: dict)
    """
    reasons = []

    # ─── 文件存在性 ──────────────────────────────────────────
    if not os.path.isfile(path):
        return False, [f"文件不存在: {path}"], {}

    # ─── 物理大小前置拦截（防 OOM）──────────────────────────
    physical_size = os.path.getsize(path)
    if physical_size > 1024 * 1024:  # 1MB
        size_kb = physical_size // 1024
        return False, [f"❌ 物理大小超限: {size_kb}KB > 1MB，拒绝读入内存"], {}

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
        lines = content.splitlines()

    # 对内容做 Unicode 正规化（用于危险模式检测）
    normalized_content = normalize_line(content)
    normalized_lines = [normalize_line(line) for line in lines]

    # 校验跟踪器 — 动态记录各项校验结果
    check_results = {}

    # ─── 1. 结构校验：签名区块（统一使用 normalized_content） ───
    struct_ok = True
    if "CHECKPOINT_CREATED_BY: TokenGuard-v4" not in normalized_content:
        reasons.append("❌ 结构校验失败: 缺少 CHECKPOINT_CREATED_BY: TokenGuard-v4 签名（必须精确匹配版本号）")
        struct_ok = False

    if "CHECKPOINT_TIME:" not in normalized_content:
        reasons.append("❌ 结构校验失败: 缺少 CHECKPOINT_TIME 时间戳")
        struct_ok = False

    if "CHECKPOINT_HASH:" not in normalized_content:
        reasons.append("❌ 结构校验失败: 缺少 CHECKPOINT_HASH 校验值")
        struct_ok = False
    else:
        # HASH 格式校验：期望 "ISO日期[T时间][±时区]-任务名" 格式
        # 任务名允许包含空格、中文等；时区偏移单独匹配避免贪婪吞并
        hash_match = re.search(
            r'CHECKPOINT_HASH:\s+\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2})?(?:[+\-]\d{2}:\d{2})?-[^\n]+',
            normalized_content
        )
        if not hash_match:
            reasons.append("❌ 结构校验失败: CHECKPOINT_HASH 格式不合规（期望如 2026-03-01T00:30:00+08:00-deploy-yuyue）")
            struct_ok = False

    check_results["结构校验"] = "签名区块完整，HASH 格式合规" if struct_ok else "失败"

    # ─── 2. 章节校验：标题层级 + 白名单 ────────────────
    section_ok = True
    found_sections = []
    for line in lines:
        stripped = line.strip()
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if heading_match:
            level = len(heading_match.group(1))
            section_name = heading_match.group(2).strip()
            if level == 1:
                if section_name != "🦞 Checkpoint State":
                    reasons.append(f"❌ 章节校验失败: 非预期一级标题 '# {section_name}'")
                    section_ok = False
            elif level == 2:
                found_sections.append(section_name)
                if section_name not in ALLOWED_SECTIONS:
                    reasons.append(f"❌ 章节校验失败: 非预期二级标题 '## {section_name}'")
                    section_ok = False
            else:
                reasons.append(f"❌ 章节校验失败: 不允许 {'#' * level} 标题 → '{stripped}'")
                section_ok = False

    if not found_sections:
        reasons.append("❌ 章节校验失败: 未找到任何 ## 章节标题")
        section_ok = False

    check_results["章节校验"] = "所有标题在白名单内，无非法层级" if section_ok else "失败"

    # ─── 3. 内容校验：危险模式检测 ─────────────────────
    content_ok = True

    # 3a. 逐行检测（对正规化后的内容）
    for i, norm_line in enumerate(normalized_lines, 1):
        for pattern in _COMPILED_DANGER:
            if pattern.search(norm_line):
                original = lines[i-1] if i-1 < len(lines) else norm_line
                safe_preview = original[:60] + "..." if len(original) > 60 else original
                reasons.append(f"❌ 内容校验失败 (L{i}): 检测到危险模式 → {safe_preview}")
                content_ok = False

    # 3b. 全文跨行检测 — 仅在 3a 未命中时作为跨行拆分攻击兜底
    if content_ok:
        for pattern_str in DANGER_PATTERNS:
            mp = re.compile(pattern_str, re.DOTALL)
            if mp.search(normalized_content):
                reasons.append("❌ 内容校验失败（跨行拆分攻击）: 全文检测命中危险模式")
                content_ok = False
                break

    check_results["内容校验"] = "未检测到危险模式（含跨行检测）" if content_ok else "失败"

    # ─── 4. 大小校验：防超长注入 ─────────────────────
    size_ok = True
    if len(lines) > 200:
        reasons.append(f"❌ 大小校验失败: state.md 有 {len(lines)} 行，超过 200 行上限")
        size_ok = False

    if len(content) > 20000:
        reasons.append(f"❌ 大小校验失败: state.md 有 {len(content)} 字符，超过 20000 字符上限")
        size_ok = False

    check_results["大小校验"] = f"文件大小在合理范围内 ({len(lines)}行/{len(content)}字符)" if size_ok else "失败"

    is_valid = len(reasons) == 0
    return is_valid, reasons, check_results


def main():
    path = sys.argv[1] if len(sys.argv) >= 2 else "state.md"

    print(f"[TokenGuard] 🔍 正在校验: {os.path.abspath(path)}")
    print("=" * 60)

    is_valid, reasons, check_results = verify_state_md(path)

    if is_valid:
        print("✅ state.md 校验通过！所有检查项均正常。")
        print("")
        print("校验结果摘要:")
        for check_name, result in check_results.items():
            print(f"  ✅ {check_name}: {result}")
        sys.exit(0)
    else:
        print("⛔ state.md 校验失败！发现以下问题：")
        print("")
        for reason in reasons:
            print(f"  {reason}")
        print("")
        print("校验项状态:")
        for check_name, result in check_results.items():
            icon = "✅" if result != "失败" else "❌"
            print(f"  {icon} {check_name}: {result}")
        print("")
        print("⚠️  Agent 禁止恢复此 state.md。请人工审阅后决定是否继续。")
        sys.exit(1)


if __name__ == "__main__":
    main()
