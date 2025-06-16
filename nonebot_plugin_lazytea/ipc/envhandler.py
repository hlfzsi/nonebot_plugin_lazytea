import re
import json
import aiofiles
from dataclasses import dataclass
from typing import Dict, Any, List, Set, Optional

from pydantic import BaseModel


@dataclass(slots=True)
class PluginBlock:
    name: str
    begin: str
    end: str
    lines: List[str]
    keys: Set[str]


@dataclass(slots=True)
class FileStructure:
    plugins: Dict[str, PluginBlock]  # 插件名到区块的快速查找
    free_lines: List[str]           # 保持原有顺序的非插件行
    all_keys: Set[str]              # 全文件键集合加速查询


class EnvWriter:

    def __init__(self, plugin_name: str):
        self.target_plugin = plugin_name.lower()
        self.plugin_begin = f"# {self.target_plugin} begin"
        self.plugin_end = f"# {self.target_plugin} end"
        self.encoding = "utf-8"
        self.key_pattern = re.compile(r"^\s*([\w-]+)\s*=")  # 预编译正则

    async def write(self, new_config: BaseModel, existed_config: BaseModel, env_file: str) -> None:
        """主写入流程"""
        new_dict = new_config.model_dump()
        existed_dict = existed_config.model_dump()

        diff_fields = {}
        same_fields = {}
        fields_to_delete = set()

        for key, new_value in new_dict.items():
            existed_value = existed_dict.get(key)
            if new_value is None:
                fields_to_delete.add(key)
            elif new_value != existed_value:
                diff_fields[key] = new_value
            else:
                same_fields[key] = new_value

        structure = await self._parse_file(env_file)

        existing_same_fields = {
            k: v for k, v in same_fields.items()
            if k in structure.all_keys
        }

        # 合并需要处理的字段
        fields_to_process = {
            **diff_fields,           # 差异字段需要写入
            **existing_same_fields   # 已存在的相同值字段需要整理
        }

        # 过滤现有键 (包括需要删除的字段)
        keys_to_filter = set(fields_to_process.keys()) | fields_to_delete
        filtered = self._filter_existing_keys(structure, keys_to_filter)

        # 构建输出 (只写入非None值的字段)
        output = self._build_output(filtered, fields_to_process)

        # 写入文件
        await self._write_output(env_file, output)

    async def _parse_file(self, path: str) -> FileStructure:
        """解析文件为结构化表示"""
        plugins = {}
        free_lines = []
        all_keys = set()
        current_block = None

        async with aiofiles.open(path, "r", encoding=self.encoding) as f:
            async for raw_line in f:
                line = raw_line.rstrip("\n")

                # 处理插件区块
                if line.startswith("#"):
                    if not current_block:
                        if block_name := self._match_plugin_begin(line):
                            current_block = PluginBlock(
                                name=block_name,
                                begin=line,
                                end="",
                                lines=[],
                                keys=set()
                            )
                    else:
                        if self._match_plugin_end(line, current_block.name):
                            current_block.end = line
                            plugins[current_block.name] = current_block
                            all_keys.update(current_block.keys)
                            current_block = None
                    continue

                if current_block:
                    key = self._extract_key(line)
                    if key:
                        current_block.keys.add(key)
                        all_keys.add(key)
                    current_block.lines.append(line)
                else:
                    key = self._extract_key(line)
                    if key:
                        all_keys.add(key)
                    free_lines.append(line)

        return FileStructure(plugins, free_lines, all_keys)

    def _filter_existing_keys(self, structure: FileStructure, target_keys: Set[str]) -> FileStructure:
        """快速过滤现有键"""
        # 计算需要过滤的键集合
        existing_keys = structure.all_keys & target_keys

        # 过滤插件区块
        new_plugins = {}
        for name, block in structure.plugins.items():
            if name == self.target_plugin:
                continue  # 跳过目标插件

            # 快速判断是否需要处理该区块
            if not (block.keys & existing_keys):
                new_plugins[name] = block
                continue

            # 需要过滤的区块
            filtered_lines = [
                line for line in block.lines
                if self._extract_key(line) not in existing_keys
            ]
            new_plugins[name] = PluginBlock(
                name=name,
                begin=block.begin,
                end=block.end,
                lines=filtered_lines,
                keys=block.keys - existing_keys
            )

        # 过滤自由行
        filtered_free = [
            line for line in structure.free_lines
            if self._extract_key(line) not in existing_keys
        ]

        return FileStructure(
            plugins=new_plugins,
            free_lines=filtered_free,
            all_keys=structure.all_keys - existing_keys
        )

    def _build_output(self, structure: FileStructure, data: Dict[str, Any]) -> List[str]:
        """构建输出内容"""
        output = []

        # 保留的非插件内容
        for line in structure.free_lines:
            output.append(line)

        # 其他插件区块
        for block in structure.plugins.values():
            output.append(block.begin)
            output.extend(block.lines)
            output.append(block.end)

        # 新增目标插件区块
        output.append(self.plugin_begin)
        output.extend(
            f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in data.items())
        output.append(self.plugin_end)

        return output

    async def _write_output(self, path: str, lines: List[str]) -> None:
        """批量写入"""
        async with aiofiles.open(path, "w", encoding=self.encoding, newline="") as f:
            await f.write("\n".join(lines))

    def _match_plugin_begin(self, line: str) -> Optional[str]:
        """快速匹配插件开始行"""
        if line.endswith(" begin") and line.startswith("# "):
            return line[2:-6].strip().lower()
        return None

    def _match_plugin_end(self, line: str, plugin_name: str) -> bool:
        """匹配插件结束行"""
        expected = f"# {plugin_name} end"
        return line.lower() == expected.lower()

    def _extract_key(self, line: str) -> Optional[str]:
        match = self.key_pattern.match(line)
        return match.group(1).lower() if match else None
