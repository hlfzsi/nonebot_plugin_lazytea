import re
from typing import Optional, Tuple


class VersionUtils:
    """
    版本处理工具类，遵循 PEP 440 规范进行版本号的解析与比较。

    PEP 440 规范定义了一种标准的版本号格式，以便于软件包的可靠排序。
    一个完整的版本号结构大致如下：
    [N!]N(.N)*[{a|b|rc}N][.postN][.devN][+local]
    """
    VERSION_PATTERN = re.compile(r"""
        ^v?                                                     # 1. 可选的 'v' 前缀，会被忽略
        (?:(?P<epoch>[0-9]+)!)?                                  # 2. 版本纪元 (Epoch)，例如: 1!
        (?P<release>[0-9]+(?:\.[0-9]+)*)                         # 3. 发布版本号，例如: 1.2.3 或 1.0
        (?P<pre>                                                # 4. 预发布版本标识 (可选)
            [-._]?
            (?P<pre_tag>a|b|rc|alpha|beta|pre|preview)
            [-._]?
            (?P<pre_num>[0-9]+)?
        )?
        (?P<post>                                               # 5. 后发布版本标识 (可选)
            (?:[-._]?
               (?P<post_tag>post|rev|r)
               [-._]?
               (?P<post_num>[0-9]+)?
            )
        )?
        (?P<dev>                                                # 6. 开发版本标识 (可选)
            [-._]?
            (?P<dev_tag>dev)
            [-._]?
            (?P<dev_num>[0-9]+)?
        )?
        (?:\+(?P<local>[a-z0-9]+(?:[-._][a-z0-9]+)*))?           # 7. 本地版本标识符 (在版本比较中被忽略)
        $
    """, re.VERBOSE | re.IGNORECASE)

    # dev < alpha < beta < rc < final < post
    _PHASE_WEIGHTS = {
        'dev': -4,
        'a': -3,      # alpha
        'b': -2,      # beta
        'rc': -1,     # release candidate
        'final': 0,   # 最终发布版
        'post': 1,    # 后发布版
    }

    _TAG_ALIASES = {
        'alpha': 'a',
        'beta': 'b',
        'pre': 'rc',
        'preview': 'rc',
        'rev': 'post',
        'r': 'post',
    }

    @classmethod
    def parse_version(cls, version_str: str) -> Optional[Tuple[int, Tuple[int, ...], Tuple[int, int]]]:
        """
        将版本字符串解析为一个可直接用于比较的元组 ( "比较键" )。

        遵循 PEP 440 的排序规则，将版本字符串转换为一个元组，
        元组的元素顺序决定了比较的优先级。

        返回格式: (纪元, (发布号元组), (阶段权重, 阶段编号))

        示例:
        - "1.2.0.dev1"  -> (0, (1, 2, 0), (-4, 1))
        - "1.2.0a1"     -> (0, (1, 2, 0), (-3, 1))
        - "1.2.0b2"     -> (0, (1, 2, 0), (-2, 2))
        - "1.2.0rc3"    -> (0, (1, 2, 0), (-1, 3))
        - "1.2.0"       -> (0, (1, 2, 0), (0, 0))  # 最终版
        - "1.2.0.post4" -> (0, (1, 2, 0), (1, 4))
        """
        match = cls.VERSION_PATTERN.match(version_str)
        if not match:
            return None

        parts = match.groupdict()

        # 1. 解析纪元 (Epoch)
        epoch = int(parts['epoch'] or 0)

        # 2. 解析发布版本号 (Release)
        release_str = parts['release']
        release = tuple(int(i) for i in release_str.split('.'))

        # 3. 解析发布阶段 (Phase)
        if parts['dev_tag']:
            phase_weight = cls._PHASE_WEIGHTS['dev']
            phase_num = int(parts['dev_num'] or 0)
        elif parts['pre_tag']:
            tag = parts['pre_tag'].lower()
            normalized_tag = cls._TAG_ALIASES.get(tag, tag)
            phase_weight = cls._PHASE_WEIGHTS[normalized_tag]
            phase_num = int(parts['pre_num'] or 0)
        elif parts['post_tag']:
            phase_weight = cls._PHASE_WEIGHTS['post']
            phase_num = int(parts['post_num'] or 0)
        else:
            phase_weight = cls._PHASE_WEIGHTS['final']
            phase_num = 0

        phase = (phase_weight, phase_num)
        return epoch, release, phase

    @classmethod
    def _normalize_keys(cls, key_a: tuple, key_b: tuple) -> Tuple[tuple, tuple]:
        """
        在比较前，对发布号部分进行归一化处理，确保长度一致。
        """
        a_epoch, a_release, a_phase = key_a
        b_epoch, b_release, b_phase = key_b
        max_len = max(len(a_release), len(b_release))
        a_release_padded = a_release + (0,) * (max_len - len(a_release))
        b_release_padded = b_release + (0,) * (max_len - len(b_release))
        key_a_padded = (a_epoch, a_release_padded, a_phase)
        key_b_padded = (b_epoch, b_release_padded, b_phase)
        return key_a_padded, key_b_padded

    @classmethod
    def compare_versions(cls, a: str, b: str) -> int:
        """
        比较两个遵循 PEP 440 规范的版本字符串。
        """
        key_a = cls.parse_version(a)
        key_b = cls.parse_version(b)

        if not key_a or not key_b:
            return 0

        key_a_norm, key_b_norm = cls._normalize_keys(key_a, key_b)

        if key_a_norm > key_b_norm:
            return 1
        if key_a_norm < key_b_norm:
            return -1
        return 0
