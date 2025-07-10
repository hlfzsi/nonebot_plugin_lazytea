from typing import Dict, List, Optional, Any, TypedDict

class PermissionListDivide(TypedDict):
    """权限列表划分，区分用户和群组"""
    user: List[str]
    group: List[str]


class MatcherPermission(TypedDict):
    """单个匹配器的权限设置"""
    white_list: PermissionListDivide
    ban_list: PermissionListDivide


class MatcherRuleModel(TypedDict):
    """单个匹配器的完整规则模型"""
    rule: Dict[str, Any]
    permission: MatcherPermission
    is_on: bool


class PluginModel(TypedDict):
    """插件模型，包含多个匹配器"""
    matchers: List[MatcherRuleModel]


class BotModel(TypedDict):
    """机器人模型，包含多个插件"""
    plugins: Dict[str, PluginModel]


class FullConfigModel(TypedDict):
    """完整的配置模型"""
    bots: Dict[str, BotModel]


class ReadableRoster:
    """
    一个可读的权限名册类，用于处理和检查权限配置。
    这是一个类级别的单例，用于在UI的生命周期内共享和操作配置数据。
    """
    config: FullConfigModel = {"bots": {}}

    @classmethod
    def update_config(cls, new_config: FullConfigModel) -> None:
        """更新全局配置"""
        cls.config = new_config

    @classmethod
    def get_config(cls) -> FullConfigModel:
        """获取当前全局配置"""
        return cls.config

    @classmethod
    def check(
        cls,
        bot: str,
        plugin: str,
        matcher_key: str,
        userid: str,
        groupid: Optional[str] = None
    ) -> bool:
        """
        核心权限检查逻辑。

        Args:
            bot (str): 机器人ID。
            plugin (str): 插件名称。
            matcher_key (str): 匹配器的可读名称。
            userid (str): 用户ID。
            groupid (Optional[str]): 群组ID，如果是私聊则为None。

        Returns:
            bool: 如果允许访问则返回True，否则返回False。
        """
        bot_config = cls.config.get("bots", {}).get(bot)
        if not bot_config:
            return True  # 机器人无特定配置，默认允许

        plugin_config = bot_config.get("plugins", {}).get(plugin)
        if not plugin_config:
            return True  # 插件无特定配置，默认允许

        for matcher in plugin_config.get("matchers", []):
            if cls._get_rule_display_name(matcher["rule"]) == matcher_key:
                return cls._evaluate_matcher_config(matcher, userid, groupid)

        return True  # 匹配器未找到，默认允许

    @classmethod
    def _evaluate_matcher_config(
        cls,
        matcher_config: MatcherRuleModel,
        userid: str,
        groupid: Optional[str]
    ) -> bool:
        """评估单个匹配器的权限"""
        is_on = matcher_config.get("is_on", True)
        permission = matcher_config["permission"]
        white_list = permission["white_list"]
        ban_list = permission["ban_list"]

        in_white_user = userid in white_list["user"]
        in_white_group = bool(groupid and groupid in white_list["group"])

        in_ban_user = userid in ban_list["user"]
        in_ban_group = bool(groupid and groupid in ban_list["group"])

        if in_ban_user or in_ban_group:
            return False

        if is_on:
            if white_list["user"] or white_list["group"]:
                return in_white_user or in_white_group
            return True
        else:
            return in_white_user or in_white_group

    @staticmethod
    def _get_rule_display_name(rule_data: dict) -> str:
        """从规则字典生成一个人类可读的名称"""
        if not rule_data:
            return "空规则"

        parts = []
        if rule_data.get("alconna_commands"):
            cmds = rule_data["alconna_commands"]
            parts.append(f"Alconna: {', '.join(cmds)}")

        if rule_data.get("commands"):
            cmds = rule_data["commands"]
            parts.append(f"命令: {', '.join('/'.join(cmd) for cmd in cmds)}")

        if rule_data.get("startswith"):
            parts.append(f"开头: {', '.join(rule_data['startswith'])}")

        if rule_data.get("endswith"):
            parts.append(f"结尾: {', '.join(rule_data['endswith'])}")

        if rule_data.get("fullmatch"):
            parts.append(f"全匹配: {', '.join(rule_data['fullmatch'])}")

        if rule_data.get("keywords"):
            parts.append(f"关键词: {', '.join(rule_data['keywords'])}")

        if rule_data.get("regex_patterns"):
            patterns = rule_data["regex_patterns"]
            display_patterns = [
                p[:30] + '...' if len(p) > 30 else p for p in patterns]
            parts.append(f"正则: {', '.join(display_patterns)}")

        if rule_data.get("to_me"):
            parts.append("@机器人")

        if rule_data.get("event_types"):
            parts.append(f"事件: {', '.join(rule_data['event_types'])}")

        if not parts:
            return "通用规则"

        return " | ".join(parts)
