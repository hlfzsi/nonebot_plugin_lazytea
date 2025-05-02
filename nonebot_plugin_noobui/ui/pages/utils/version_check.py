import re
from typing import Optional, Tuple


class VersionUtils:
    """版本处理工具类"""
    @staticmethod
    def parse_version(version_str: str) -> Optional[Tuple[list, tuple]]:
        version_str = version_str.lstrip('v').lower()
        pattern = r"""
            ^ 
            (\d+)\.(\d+)\.(\d+)           # 主版本号 
            (?:[-.]?(?:
                (a|alpha|b|beta|pre|rc)    # 预发布类型 (now includes 'a' and 'b')
                (?:\.?(\d+))?             # 预发布编号 
                |
                (post)                     # 后发布版本 
                (?:\.?(\d+))?
            ))?
            (?:[+-](\w+))?                 # build元数据 
            $
        """
        match = re.match(pattern,  version_str, re.VERBOSE)
        if not match:
            return None

        major, minor, patch = map(int, match.groups()[:3])
        pre_type, pre_num, post_type, post_num, build = match.groups()[3:]

        version = [major, minor, patch]
        suffix = (0, 0)  # (类型权重, 编号)

        if pre_type:
            type_weights = {'pre': 1, 'a': 2,
                            'alpha': 2, 'b': 3, 'beta': 3, 'rc': 4}
            normalized_type = pre_type
            suffix = (type_weights.get(normalized_type,  5), int(pre_num or 0))
        elif post_type:
            suffix = (5, int(post_num or 0))

        return (version, suffix)

    @classmethod
    def compare_versions(cls, a: str, b: str) -> int:
        """比较两个版本号"""
        va = cls.parse_version(a)
        vb = cls.parse_version(b)
        if not va or not vb:
            return 0

        # 比较主版本号
        for x, y in zip(va[0], vb[0]):
            if x != y:
                return x - y

        # 比较后缀
        return (va[1][0] - vb[1][0]) or (va[1][1] - vb[1][1])
