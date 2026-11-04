"""技能发现与完整读取共用的有界YAML头部读取，不解析技能执行内容。"""

from pathlib import Path


def read_skill_header(path: Path) -> str:
    """按字节行读取开头的---头部，最多64KiB，不把正文和参考文件全部读入。

    兼容UTF-8 BOM及Windows换行；未找到闭合分隔符时报告错误。
    这只是元数据发现，不是read_skill的完整正文读取能力。
    """
    limit = 65536
    with path.open("rb") as stream:
        first = stream.readline(limit + 1)
        if len(first) > limit or first.decode("utf-8-sig").strip() != "---":
            raise ValueError("SKILL.md必须以YAML头部分隔符---开始。")
        used = len(first)
        lines: list[str] = []
        while used < limit:
            line = stream.readline(limit - used + 1)
            used += len(line)
            if used > limit:
                break
            if not line:
                raise ValueError("SKILL.md的YAML头部缺少结束分隔符---。")
            text = line.decode("utf-8")
            if text.strip() == "---":
                return "".join(lines)
            lines.append(text)
    raise ValueError("SKILL.md头部超过64KiB读取上限。")
