import logging
from typing import Any, Dict, List

from app.agents.shared import extract_json_block
from app.core.config import settings
from app.core.llm import invoke_llm_with_fallback

logger = logging.getLogger(__name__)


class BaseTaskExecutionAgent:
    name = "task_execution_agent"
    max_steps = 6

    def run(self, state: Dict[str, Any], task: Dict[str, Any] | None = None) -> Dict[str, Any]:
        task = task or {}
        context = self.build_initial_context(state, task)
        trace: List[Dict[str, Any]] = []

        for step_index in range(self.max_steps):
            action = self.decide_action(state, task, context, trace, step_index)
            trace.append(
                {
                    "step": step_index + 1,
                    "task_title": task.get("title", self.name),
                    "task_goal": task.get("goal", ""),
                    "thought": action.get("thought", ""),
                    "action": action.get("action", "finish"),
                    "target": action.get("target", ""),
                }
            )

            if action.get("action") == "finish":
                if not self.finish_allowed(state, task, context, trace, step_index):
                    action = self.fallback_action(state, task, context, [item for item in self.available_actions(state, task, context) if item != "finish"], step_index)
                    trace[-1]["thought"] = action.get("thought", "")
                    trace[-1]["action"] = action.get("action", "finish")
                    trace[-1]["target"] = action.get("target", "")
                else:
                    break

            context = self.perform_action(state, task, context, action, trace[-1])
            if self.should_finish(state, task, context, trace):
                trace.append(
                    {
                        "step": step_index + 1,
                        "task_title": task.get("title", self.name),
                        "task_goal": task.get("goal", ""),
                        "thought": "当前任务上下文已经足够，进入输出阶段。",
                        "action": "finish",
                        "target": "",
                    }
                )
                break

        return self.finalize(state, task, context, trace)

    def build_initial_context(self, state: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def available_actions(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        raise NotImplementedError

    def build_prompt(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any], trace: List[Dict[str, Any]], step_index: int) -> str:
        recent_trace = trace[-2:]
        return f"""
你是 {self.name}，正在执行一个受控任务循环。
城市：{state.get('city', '')}
用户需求：{state.get('query', '')}
任务标题：{task.get('title', self.name)}
任务目标：{task.get('goal', '')}
当前第 {step_index + 1} 步，最多 {self.max_steps} 步。
可选动作：{self.available_actions(state, task, context)}
当前上下文摘要：{self.context_summary(context)}
最近轨迹：{recent_trace}

只返回 JSON：
{{
  "thought": "一句话说明下一步为什么这样做",
  "action": "必须从可选动作中选择",
  "target": "如果需要，填入本步要处理的对象名；否则为空字符串"
}}
"""

    def decide_action(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any], trace: List[Dict[str, Any]], step_index: int) -> Dict[str, Any]:
        available = self.available_actions(state, task, context)
        if not available:
            return {"thought": "没有剩余可执行动作，结束任务。", "action": "finish", "target": ""}

        try:
            response = invoke_llm_with_fallback(
                self.build_prompt(state, task, context, trace, step_index),
                temperature=0.1,
                max_tokens=220,
                request_timeout=12,
                max_retries=0,
                provider_order=[state.get("provider", settings.DEFAULT_LLM_PROVIDER), "deepseek", "openai", "anthropic", "google"],
            )
            content = response.content if isinstance(response.content, str) else str(response.content)
            parsed = extract_json_block(content)
            if isinstance(parsed, dict):
                action = str(parsed.get("action", "")).strip()
                if action in available:
                    return {
                        "thought": str(parsed.get("thought", "")).strip() or "继续执行下一步。",
                        "action": action,
                        "target": str(parsed.get("target", "")).strip(),
                    }
        except Exception as exc:
            logger.info("%s llm execution fallback: %s", self.name, exc)

        return self.fallback_action(state, task, context, available, step_index)

    def fallback_action(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any], available: List[str], step_index: int) -> Dict[str, Any]:
        next_action = available[0] if available else "finish"
        return {
            "thought": "按预设顺序执行下一步。",
            "action": next_action,
            "target": "",
        }

    def perform_action(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any], action: Dict[str, Any], trace_entry: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def should_finish(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any], trace: List[Dict[str, Any]]) -> bool:
        return False

    def finish_allowed(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any], trace: List[Dict[str, Any]], step_index: int) -> bool:
        return self.should_finish(state, task, context, trace) or not self.available_actions(state, task, context) or self.available_actions(state, task, context) == ["finish"]

    def finalize(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any], trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        raise NotImplementedError

    def context_summary(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: value
            for key, value in context.items()
            if key in {"pending_pairs", "built_legs", "total_activities", "completed_activities", "poi_count"}
        }
