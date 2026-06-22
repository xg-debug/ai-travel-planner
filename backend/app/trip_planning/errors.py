from __future__ import annotations

from typing import Any, Dict


def classify_planning_error(error: Any) -> Dict[str, Any]:
    text = str(error or "")
    lower = text.lower()

    if "insufficient balance" in lower or "payment required" in lower or "402" in lower or "余额不足" in text:
        return {
            "code": "LLM_INSUFFICIENT_BALANCE",
            "message": "AI 服务余额不足，当前无法继续生成行程。请充值或切换到可用模型后再试。",
            "retryable": False,
            "operator_action": "检查 DeepSeek/OpenAI 等模型账户余额，或在后台切换可用模型。",
        }

    if (
        "invalid_api_key" in lower
        or "api key not valid" in lower
        or "invalid x-api-key" in lower
        or "incorrect api key" in lower
        or "authentication_error" in lower
    ):
        return {
            "code": "LLM_INVALID_API_KEY",
            "message": "AI 模型密钥无效，当前无法生成行程。请在后台配置真实可用的模型 Key。",
            "retryable": False,
            "operator_action": "检查后端环境变量或管理后台中的模型 API Key。",
        }

    if "未检测到可用的 llm api key" in lower or "未配置" in text:
        return {
            "code": "LLM_NOT_CONFIGURED",
            "message": "未配置可用的 AI 模型密钥，请先完成模型服务配置。",
            "retryable": False,
            "operator_action": "配置 OpenAI/Anthropic/Google/DeepSeek 任一可用模型 Key。",
        }

    if "rate limit" in lower or "429" in lower or "quota" in lower or "限流" in text:
        return {
            "code": "LLM_RATE_LIMITED",
            "message": "AI 服务当前请求过多，请稍后再试。",
            "retryable": True,
            "operator_action": "等待限流恢复，或切换到备用模型。",
        }

    if "timed out" in lower or "timeout" in lower or "超时" in text:
        return {
            "code": "LLM_TIMEOUT",
            "message": "AI 服务响应超时，请稍后重试。",
            "retryable": True,
            "operator_action": "检查模型服务连通性，必要时增大请求超时时间。",
        }

    if "所有模型调用失败" in text:
        return {
            "code": "LLM_ALL_PROVIDERS_FAILED",
            "message": "所有 AI 模型调用均失败，请检查模型服务配置后再试。",
            "retryable": False,
            "operator_action": "检查默认模型、备用模型、API Key 和账户状态。",
        }

    if "真实景点候选不足" in text:
        return {
            "code": "INSUFFICIENT_ATTRACTIONS",
            "message": "未查询到足够的真实景点数据，请换一个更具体的目的地后重试。",
            "retryable": True,
            "operator_action": "检查地图服务配置或优化目的地输入。",
        }

    if "真实餐饮候选不足" in text:
        return {
            "code": "INSUFFICIENT_FOODS",
            "message": "未查询到足够的真实餐饮数据，请换一个更具体的目的地后重试。",
            "retryable": True,
            "operator_action": "检查地图服务配置或优化目的地输入。",
        }

    return {
        "code": "PLANNING_FAILED",
        "message": "行程规划失败，请稍后重试。",
        "retryable": True,
        "operator_action": "查看后端日志定位具体失败原因。",
    }


def friendly_planning_error(error: Any) -> str:
    return str(classify_planning_error(error)["message"])

