# 极度简单的函数哈希，但应当足够
import ast
import hashlib
import inspect
import io
from functools import lru_cache

@lru_cache(maxsize=None)
def get_function_fingerprint(func):
    """
    获取Python函数的稳定特征指纹
    
    参数:
        func: 要分析的函数对象
        
    返回:
        返回一个SHA256哈希字符串，在不同平台和Python版本下对相同函数逻辑保持稳定
    """
    source = inspect.getsource(func)

    tree = ast.parse(source)

    if not isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ValueError("提供的对象不是函数定义")

    feature_extractor = FunctionFeatureExtractor()
    feature_extractor.visit(tree)

    features = feature_extractor.features

    feature_str = io.StringIO()
    feature_str.write(f"name:{features['name']}\n")
    feature_str.write(f"args:{','.join(features['args'])}\n")
    feature_str.write(f"returns:{features['returns']}\n")

    for stmt in features['body']:
        feature_str.write(f"stmt:{stmt}\n")

    return hashlib.sha256(feature_str.getvalue().encode('utf-8')).hexdigest()


class FunctionFeatureExtractor(ast.NodeVisitor):
    """提取函数的稳定特征"""
    def __init__(self):
        self.features = {
            'name': '',
            'args': [],
            'returns': '',
            'body': []
        }

    def visit_FunctionDef(self, node):
        self.features['name'] = node.name

        self.features['args'] = [arg.arg for arg in node.args.args]
        if node.args.vararg:
            self.features['args'].append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            self.features['args'].append(f"**{node.args.kwarg.arg}")

        self.features['returns'] = self._get_annotation(node.returns)

        for stmt in node.body:
            self.features['body'].append(self._stmt_to_string(stmt))

    def _get_annotation(self, node):
        """获取类型注解的字符串表示"""
        if node is None:
            return 'none'
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Constant):
            return str(node.value)
        return 'complex_annotation'

    def _stmt_to_string(self, node):
        """将语句转换为稳定的字符串表示"""
        if isinstance(node, ast.Return):
            return f"return {self._expr_to_string(node.value)}"
        if isinstance(node, ast.Assign):
            targets = '='.join(self._expr_to_string(t) for t in node.targets)
            return f"{targets}={self._expr_to_string(node.value)}"
        if isinstance(node, ast.Expr):
            return self._expr_to_string(node.value)
        if isinstance(node, ast.If):
            test = self._expr_to_string(node.test)
            return f"if {test}:...else:..."
        return "generic_statement"

    def _expr_to_string(self, node):
        """将表达式转换为稳定的字符串表示"""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Constant):
            return str(node.value)
        if isinstance(node, ast.Call):
            func = self._expr_to_string(node.func)
            args = ','.join(self._expr_to_string(arg) for arg in node.args)
            return f"{func}({args})"
        if isinstance(node, ast.Attribute):
            value = self._expr_to_string(node.value)
            return f"{value}.{node.attr}"
        return "generic_expression"