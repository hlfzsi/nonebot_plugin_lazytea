import ast
import hashlib
import inspect
from typing import Callable, Dict, Set


class CacheForFingerprint:
    cache: Dict[Callable, str] = {}
    reversed_cache: Dict[str, Callable] = {}

    @classmethod
    def store(cls, plugin_name: str, k: Callable, v: str):
        cls.cache[k] = v
        cls.reversed_cache[f"{plugin_name}{v}"] = k

    @classmethod
    def reverse(cls, plugin_name: str, v: str):
        return cls.reversed_cache.get(f"{plugin_name}{v}")

    @classmethod
    def flit(cls, raw_set: Set[Callable], set_to_remove: Set[str], plugin_name: str) -> Set[Callable]:
        to_remove = {cls.reverse(plugin_name, v) for v in set_to_remove}
        return raw_set - to_remove


def get_function_fingerprint(plugin_name: str, func: Callable) -> str:
    """
    获取Python函数的稳定特征指纹

    参数:
        func: 要分析的函数对象

    返回:
        返回一个SHA256哈希字符串，在不同平台和Python版本下对相同函数逻辑保持稳定

    异常:
        ValueError: 当输入不是函数或无法解析函数时抛出
    """
    try:
        if func in CacheForFingerprint.cache:
            return CacheForFingerprint.cache[func]
        source = inspect.getsource(func)
        tree = ast.parse(source)

        if not isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise ValueError("提供的对象不是函数定义")

        ast_dump = ast.dump(tree, annotate_fields=False,
                            include_attributes=False)

        hash_obj = hashlib.sha256()
        hash_obj.update(ast_dump.encode('utf-8'))
        hash_final = hash_obj.hexdigest()
        CacheForFingerprint.store(plugin_name, func, hash_final)
        return hash_final

    except Exception as e:
        raise ValueError(f"无法生成函数指纹: {str(e)}")
