from pathlib import Path
import aiofiles
from typing import Dict, Optional, Set
from nonebot.matcher import Matcher
from nonebot.plugin import get_loaded_plugins
from nonebot import get_bots, logger
from nonebot_plugin_localstore import get_data_dir


from .model import MatcherRuleModel, BotPlugins, PluginMatchers


class FuncTeller:
    path: Optional[Path] = None
    data: Optional[MatcherRuleModel] = None

    @classmethod
    async def sync(cls, data_json: str) -> None:
        try:
            cls.data = MatcherRuleModel.from_json(data_json)
            await cls.save(cls.data)
        except:
            import traceback
            traceback.print_exc()

    @classmethod
    def get_matchers(cls) -> MatcherRuleModel:
        """获取所有插件的匹配器信息

        收集内容包括：
        - 机器人ID
        - 插件名称
        - 匹配器规则(RuleData)
        - 权限配置(白名单/黑名单)
        """
        if cls.path is None:
            cls.path = get_data_dir("LazyTea") / "perm.json"

        plugins = get_loaded_plugins()
        plugins = sorted(plugins, key=lambda plugin: plugin.name.lower())

        bots = sorted(list(get_bots().keys()))

        raw_matchers: Dict[str, Dict[str, Set[Matcher]]] = {}
        for bot_id in bots:
            logger.debug(f"Collecting matchers for bot: {bot_id}")
            raw_matchers[bot_id] = {  # type: ignore
                plugin.name: set(plugin.matcher) for plugin in plugins
            }

        return MatcherRuleModel.from_matchers(raw_matchers)

    @classmethod
    async def save(cls, data: MatcherRuleModel) -> None:
        """保存数据到文件"""
        if cls.path is None:
            cls.path = get_data_dir("LazyTea") / "perm.json"

        target_path = cls.path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(target_path, 'w', encoding='utf-8') as f:
            await f.write(data.model_dump_json(indent=4))

    @classmethod
    async def load(cls) -> MatcherRuleModel:
        """从文件加载数据

        Returns:
            加载的规则模型实例
        """
        if cls.path is None:
            cls.path = get_data_dir("LazyTea") / "perm.json"

        target_path = cls.path
        try:
            async with aiofiles.open(target_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                return MatcherRuleModel.from_json(content)
        except FileNotFoundError:
            logger.debug("Permission file not found, creating new one")
            return MatcherRuleModel()
        except Exception as e:
            logger.error(f"Error loading permission file: {e}")
            return MatcherRuleModel()

    @classmethod
    async def init_model(cls) -> MatcherRuleModel:
        """初始化规则模型（修正版）"""
        file_data = await cls.load()
        current_data = cls.get_matchers()
        merged_data = MatcherRuleModel()

        for bot_id, bot_plugins in current_data.bots.items():
            merged_data.bots[bot_id] = BotPlugins()

            for plugin_name, plugin_matchers in bot_plugins.plugins.items():
                merged_plugin = PluginMatchers()

                file_bot_plugins = file_data.bots.get(bot_id, None)
                if isinstance(file_bot_plugins, BotPlugins):
                    file_plugin = file_bot_plugins.plugins.get(
                        plugin_name, None)
                else:
                    file_plugin = None

                file_rule_infos = {}
                if file_plugin:
                    for matcher_info in file_plugin.matchers:
                        file_rule_infos[hash(matcher_info.rule)] = {
                            "permission": matcher_info.permission,
                            "is_on": matcher_info.is_on
                        }

                # 合并当前规则
                for current_info in plugin_matchers.matchers:
                    rule_hash = hash(current_info.rule)
                    merged_info = current_info.model_copy(deep=True)

                    # 如果文件中有相同规则，继承权限和开关状态
                    if rule_hash in file_rule_infos:
                        file_info = file_rule_infos[rule_hash]
                        merged_info.permission = file_info["permission"]
                        merged_info.is_on = file_info["is_on"]

                    merged_plugin.matchers.add(merged_info)

                merged_plugin.rebuild_rule_mapping()
                merged_data.bots[bot_id].plugins[plugin_name] = merged_plugin

        await cls.save(merged_data)
        return merged_data

    @classmethod
    async def get_model(cls) -> MatcherRuleModel:
        if not cls.data:
            cls.data = await cls.init_model()
        return cls.data
