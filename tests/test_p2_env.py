"""p2_env.py 单元测试 (tmp_path 假 .env, 不触网)."""

import pathlib
import sys

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT))
import p2_env as pe

GOOD_ENV = """FAST_LLM="deepseek:deepseek-chat"
SMART_LLM="deepseek:deepseek-chat"
STRATEGIC_LLM="deepseek:deepseek-reasoner"
DEEPSEEK_API_KEY="sk-test-fake-key-not-a-real-secret"
RETRIEVER="duckduckgo"
"""


# ---------- write-template ----------

def test_write_template_creates(tmp_path, capsys):
    env = tmp_path / ".env"
    assert pe.write_template(env) == 0
    text = env.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY" in text and "sk-REPLACE_ME" in text
    assert "RETRIEVER=" in text and "duckduckgo" in text
    assert "✅" in capsys.readouterr().out


def test_write_template_no_overwrite(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text("CUSTOM=1\n", encoding="utf-8")
    assert pe.write_template(env) == 1  # 已存在 → 跳过
    assert env.read_text(encoding="utf-8") == "CUSTOM=1\n"
    assert "未覆盖" in capsys.readouterr().out


def test_write_template_force(tmp_path):
    env = tmp_path / ".env"
    env.write_text("CUSTOM=1\n", encoding="utf-8")
    assert pe.write_template(env, force=True) == 0
    assert "sk-REPLACE_ME" in env.read_text(encoding="utf-8")


# ---------- validate ----------

def test_validate_good(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text(GOOD_ENV, encoding="utf-8")
    assert pe.validate(env) == 0
    assert "校验通过" in capsys.readouterr().out


def test_validate_placeholder_key(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text(
        GOOD_ENV.replace('DEEPSEEK_API_KEY="sk-test-fake-key-not-a-real-secret"',
                         'DEEPSEEK_API_KEY="sk-REPLACE_ME"'),
        encoding="utf-8")
    assert pe.validate(env) == 1
    assert "未填写" in capsys.readouterr().out


def test_validate_suspicious_key_format(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text(GOOD_ENV.replace("sk-test-fake-key-not-a-real-secret", "short"), encoding="utf-8")
    assert pe.validate(env) == 1
    assert "格式可疑" in capsys.readouterr().out


def test_validate_bad_model_and_retriever(tmp_path, capsys):
    env = tmp_path / ".env"
    bad = (GOOD_ENV
           .replace("deepseek:deepseek-chat", "openai:gpt-4")
           .replace('RETRIEVER="duckduckgo"', 'RETRIEVER="bogus"'))
    env.write_text(bad, encoding="utf-8")
    assert pe.validate(env) == 1
    out = capsys.readouterr().out
    assert "FAST_LLM" in out and "RETRIEVER" in out


def test_validate_tavily_warns(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text(GOOD_ENV.replace('RETRIEVER="duckduckgo"', 'RETRIEVER="tavily"'),
                   encoding="utf-8")
    assert pe.validate(env) == 1
    assert "tavily" in capsys.readouterr().out


def test_validate_missing_file(tmp_path, capsys):
    assert pe.validate(tmp_path / "nope.env") == 2
    assert "不存在" in capsys.readouterr().err


def test_validate_quoted_values(tmp_path):
    """单引号/无引号值也应正确解析。"""
    env = tmp_path / ".env"
    env.write_text(GOOD_ENV.replace('"', "'"), encoding="utf-8")
    assert pe.validate(env) == 0
