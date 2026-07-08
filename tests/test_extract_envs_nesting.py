"""测试 _extract_envs 对同类型嵌套环境的正确处理。

覆盖两个回归用例:
1. itemize 嵌套 itemize (对应 ENV_50 的 bug)
2. enumerate 嵌套 enumerate (对应 ENV_24 的 bug)
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.formats.latex.parser import LatexParser


class ExtractEnvsNestingTests(unittest.TestCase):
    """验证 _extract_envs 的同类型嵌套环境边界修正。"""

    def setUp(self):
        self.parser = LatexParser(dir=".", output_dir=".")

    def test_nested_itemize_boundary(self):
        """itemize 嵌套 itemize: 外层 \end{itemize} 不应遗留在 tex 中。"""
        tex = (
            r"\begin{itemize}" "\n"
            r"    \item OS: Linux" "\n"
            r"    \item Key Libraries:" "\n"
            r"    \begin{itemize}" "\n"
            r"        \item PyTorch: 2.3.0" "\n"
            r"        \item Transformers: 4.43.3" "\n"
            r"    \end{itemize}" "\n"
            r"\end{itemize}"
        )
        result = self.parser._extract_envs(tex)

        # \begin{itemize} 和 \end{itemize} 都不应遗留在最终 tex 中
        self.assertNotIn(r"\end{itemize}", result)
        self.assertNotIn(r"\begin{itemize}", result)

        # 提取了 2 个环境（内层+外层）
        self.assertEqual(len(self.parser.envs_json), 2)

        # 每个 env 都应有配对的 begin/end
        for env in self.parser.envs_json:
            self.assertEqual(
                env["content"].count(r"\begin{itemize}"),
                env["content"].count(r"\end{itemize}"),
            )

        # 外层 env (第二个提取) 的 content 应包含内层占位符
        outer_env = self.parser.envs_json[1]
        self.assertIn(self.parser.envs_json[0]["placeholder"], outer_env["content"])

    def test_nested_enumerate_boundary(self):
        """enumerate 嵌套 enumerate: 外层 \end{enumerate} 不应遗留在 tex 中。"""
        tex = (
            r"\begin{enumerate}" "\n"
            r"    \item First step:" "\n"
            r"    \begin{enumerate}" "\n"
            r"        \item Sub-step A" "\n"
            r"        \item Sub-step B" "\n"
            r"    \end{enumerate}" "\n"
            r"    \item Second step" "\n"
            r"\end{enumerate}"
        )
        result = self.parser._extract_envs(tex)

        self.assertNotIn(r"\end{enumerate}", result)
        self.assertNotIn(r"\begin{enumerate}", result)

        self.assertEqual(len(self.parser.envs_json), 2)

        for env in self.parser.envs_json:
            self.assertEqual(
                env["content"].count(r"\begin{enumerate}"),
                env["content"].count(r"\end{enumerate}"),
            )

    def test_three_level_nesting(self):
        """三层同类型嵌套也能正确配对。"""
        tex = (
            r"\begin{itemize}" "\n"
            r"    \item L1" "\n"
            r"    \begin{itemize}" "\n"
            r"        \item L2" "\n"
            r"        \begin{itemize}" "\n"
            r"            \item L3-A" "\n"
            r"            \item L3-B" "\n"
            r"        \end{itemize}" "\n"
            r"    \end{itemize}" "\n"
            r"\end{itemize}"
        )
        result = self.parser._extract_envs(tex)

        # 结果中不应有残留的 \begin{itemize} 或 \end{itemize}
        self.assertNotIn(r"\begin{itemize}", result)
        self.assertNotIn(r"\end{itemize}", result)

        self.assertEqual(len(self.parser.envs_json), 3)

        # 每个 env 都应配对
        for env in self.parser.envs_json:
            self.assertEqual(
                env["content"].count(r"\begin{itemize}"),
                env["content"].count(r"\end{itemize}"),
            )

    def test_mixed_nesting_unchanged(self):
        """不同类型环境嵌套（itemize 内嵌 enumerate）不受影响。
        注意：itemize 内嵌 enumerate 时，外层 itemize 的 \\end{itemize} 是唯一的，
        非贪婪匹配会正确匹配整个 itemize 块，内层 enumerate 不会被单独提取。
        这不是 bug——不同类型嵌套不存在「匹配到内层 end」的问题。
        """
        tex = (
            r"\begin{itemize}" "\n"
            r"    \item Item A" "\n"
            r"    \begin{enumerate}" "\n"
            r"        \item Enum 1" "\n"
            r"        \item Enum 2" "\n"
            r"    \end{enumerate}" "\n"
            r"    \item Item B" "\n"
            r"\end{itemize}"
        )
        result = self.parser._extract_envs(tex)

        self.assertNotIn(r"\begin{itemize}", result)
        self.assertNotIn(r"\begin{enumerate}", result)
        self.assertEqual(len(self.parser.envs_json), 1)

    def test_no_nesting_unchanged(self):
        """单层环境不受影响。"""
        tex = (
            r"\begin{itemize}" "\n"
            r"    \item A" "\n"
            r"    \item B" "\n"
            r"\end{itemize}"
        )
        result = self.parser._extract_envs(tex)

        self.assertNotIn(r"\begin{itemize}", result)
        self.assertNotIn(r"\end{itemize}", result)
        self.assertEqual(len(self.parser.envs_json), 1)

        env = self.parser.envs_json[0]
        self.assertEqual(
            env["content"].count(r"\begin{itemize}"),
            env["content"].count(r"\end{itemize}"),
        )

    # --- 回归测试：模拟 ENV_50 场景 ---

    def test_env50_regression(self):
        """ENV_50 回归：itemize 嵌套 itemize，section 在 env 后面不应有残留。"""
        # 模拟 "软件环境" section 的完整文本
        tex = (
            r"\subsection{Software Environment}" "\n\n"
            r"The software environment for all experiments consisted of:" "\n\n"
            r"\begin{itemize}" "\n"
            r"    \item \textbf{Operating System:} Linux" "\n"
            r"    \item \textbf{CUDA Version:} 12.2" "\n"
            r"    \item \textbf{NVIDIA Driver Version:} 535.54.03" "\n"
            r"    \item \textbf{Python Version:} 3.10.5" "\n"
            r"    \item \textbf{Key Libraries:}" "\n"
            r"    \begin{itemize}" "\n"
            r"        \item PyTorch: 2.3.0" "\n"
            r"        \item Transformers: 4.43.3" "\n"
            r"    \end{itemize}" "\n"
            r"\end{itemize}" "\n\n"
            r"This configuration remained consistent..."
        )
        result = self.parser._extract_envs(tex)

        # 最终 tex 中不应有残留的 \end{itemize}
        self.assertNotIn(r"\end{itemize}", result)
        self.assertNotIn(r"\begin{itemize}", result)


if __name__ == "__main__":
    unittest.main()
