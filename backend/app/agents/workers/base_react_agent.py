import logging
from typing import Any, Callable, Dict, List

from app.agents.shared import dedupe, extract_json_block
from app.core.config import settings
from app.core.llm import invoke_llm_with_fallback

logger = logging.getLogger(__name__)

ToolRunner = Callable[[str, str, int], List[Dict[str, Any]]]


class BaseReActAgent:
    name = "react_agent"
    max_steps = 3
    tool_name = "search"
    result_limit = 10
    min_target_results = 6

    def __init__(self, tool_runner: ToolRunner):
        self.tool_runner = tool_runner

    def run(self, state: Dict[str, Any], queries: List[str], task: Dict[str, Any] | None = None) -> Dict[str, Any]:
        city = state["city"]
        pending_queries = self._build_query_queue(queries, city)
        trace: List[Dict[str, Any]] = []
        collected: List[Dict[str, Any]] = []
        task = task or {}
        goal = str(task.get("goal", "")).strip()
        title = str(task.get("title", "")).strip()

        for step_index in range(self.max_steps):
            action = self._decide_action(state, pending_queries, collected, trace, step_index, goal, title)
            trace.append(
                {
                    "step": step_index + 1,
                    "task_title": title,
                    "task_goal": goal,
                    "thought": action.get("thought", ""),
                    "action": action.get("action", "finish"),
                    "query": action.get("query", ""),
                }
            )
            if action.get("action") == "finish":
                break

            query = str(action.get("query", "")).strip()
            if not query:
                break

            try:
                raw_results = self.tool_runner(query, city, 8)
            except Exception as exc:
                logger.warning("%s tool execution failed query=%s error=%s", self.name, query, exc)
                trace[-1]["observation"] = f"tool_error: {exc}"
                continue

            ranked_results = self._rank_results(raw_results, state, query)
            collected.extend(ranked_results)
            pending_queries = [item for item in pending_queries if item != query]
            trace[-1]["observation"] = self._build_observation(ranked_results)

            if self._should_finish(collected, pending_queries):
                trace.append(
                    {
                        "step": step_index + 1,
                        "thought": "当前候选结果已经足够，可进入收敛和输出阶段。",
                        "action": "finish",
                        "query": "",
                    }
                )
                break

        return self._finalize(collected, trace, goal, title)

    def _build_query_queue(self, queries: List[str], city: str) -> List[str]:
        queue: List[str] = []
        for query in queries:
            queue.extend(self.expand_query(query, city))
        return dedupe(queue)

    def expand_query(self, query: str, city: str) -> List[str]:
        return [query]

    def _decide_action(self, state: Dict[str, Any], pending_queries: List[str], collected: List[Dict[str, Any]], trace: List[Dict[str, Any]], step_index: int, goal: str, title: str) -> Dict[str, Any]:
        if not pending_queries:
            return {"thought": "没有剩余可执行查询，结束当前任务。", "action": "finish"}
        action = self._decide_action_with_llm(state, pending_queries, collected, trace, step_index, goal, title)
        if action:
            return action
        return self._fallback_action(pending_queries, collected, step_index)

    def _decide_action_with_llm(self, state: Dict[str, Any], pending_queries: List[str], collected: List[Dict[str, Any]], trace: List[Dict[str, Any]], step_index: int, goal: str, title: str) -> Dict[str, Any] | None:
        try:
            response = invoke_llm_with_fallback(
                self._build_react_prompt(state, pending_queries, collected, trace, step_index, goal, title),
                temperature=0.1,
                max_tokens=220,
                request_timeout=12,
                max_retries=0,
                provider_order=[state.get("provider", settings.DEFAULT_LLM_PROVIDER), "deepseek", "openai", "anthropic", "google"],
            )
            content = response.content if isinstance(response.content, str) else str(response.content)
            parsed = extract_json_block(content)
            if not isinstance(parsed, dict):
                return None
            action = str(parsed.get("action", "")).strip()
            query = str(parsed.get("query", "")).strip()
            if action == "finish":
                if not self._finish_allowed(collected, pending_queries, step_index):
                    return None
                return {"thought": str(parsed.get("thought", "")).strip() or "信息已经足够，结束任务。", "action": "finish", "query": ""}
            if action == self.tool_name and query in pending_queries:
                return {"thought": str(parsed.get("thought", "")).strip() or "继续搜索下一条候选查询。", "action": action, "query": query}
        except Exception as exc:
            logger.info("%s llm react planning fallback: %s", self.name, exc)
        return None

    def _build_react_prompt(self, state: Dict[str, Any], pending_queries: List[str], collected: List[Dict[str, Any]], trace: List[Dict[str, Any]], step_index: int, goal: str, title: str) -> str:
        recent_trace = trace[-2:]
        return f"""
你是 {self.name}，正在执行一个受控 ReAct 循环，只能执行一种工具或结束任务。
城市：{state['city']}
用户需求：{state['query']}
任务标题：{title or self.name}
任务目标：{goal or '尽可能收集高质量候选并输出结构化结果'}
当前是第 {step_index + 1} 步，最多 {self.max_steps} 步。
待选查询：{pending_queries[:6]}
当前累计候选数：{len(collected)}
最近观察：{recent_trace}

你只能返回 JSON：
{{
  "thought": "一句话说明为什么这样选",
  "action": "{self.tool_name} 或 finish",
  "query": "如果 action 不是 finish，则必须从待选查询中原样选择一项"
}}
"""

    def _fallback_action(self, pending_queries: List[str], collected: List[Dict[str, Any]], step_index: int) -> Dict[str, Any]:
        if not pending_queries:
            return {"thought": "没有可继续搜索的查询。", "action": "finish"}
        if self._finish_allowed(collected, pending_queries, step_index):
            return {"thought": "候选结果已经足够，直接结束。", "action": "finish"}
        return {"thought": "继续执行下一条最有价值的查询。", "action": self.tool_name, "query": pending_queries[0]}

    def _should_finish(self, collected: List[Dict[str, Any]], pending_queries: List[str]) -> bool:
        return len(self._dedupe_and_sort(collected)) >= self.min_target_results or not pending_queries

    def _finish_allowed(self, collected: List[Dict[str, Any]], pending_queries: List[str], step_index: int) -> bool:
        if not pending_queries:
            return True
        return len(self._dedupe_and_sort(collected)) >= self.min_target_results and step_index >= 1

    def _build_observation(self, results: List[Dict[str, Any]]) -> str:
        top_names = [str(item.get("name", "")).strip() for item in results[:3] if item.get("name")]
        return f"返回 {len(results)} 个候选，优先结果：{'、'.join(top_names) if top_names else '无'}"

    def _dedupe_and_sort(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        best_by_name: Dict[str, Dict[str, Any]] = {}
        for item in items:
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            current = best_by_name.get(name)
            if not current or float(item.get("_react_score", 0)) > float(current.get("_react_score", 0)):
                best_by_name[name] = item
        sorted_items = sorted(best_by_name.values(), key=lambda item: float(item.get("_react_score", 0)), reverse=True)
        for item in sorted_items:
            item.pop("_react_score", None)
        return sorted_items[: self.result_limit]

    def _finalize(self, collected: List[Dict[str, Any]], trace: List[Dict[str, Any]], goal: str, title: str) -> Dict[str, Any]:
        deduped_items = self._dedupe_and_sort(collected)
        return {
            "items": deduped_items,
            "react_trace": trace,
            "react_summary": {
                "agent": self.name,
                "task_title": title,
                "task_goal": goal,
                "steps": len([item for item in trace if item.get("action")]),
                "tool_calls": len([item for item in trace if item.get("action") == self.tool_name]),
                "result_count": len(deduped_items),
            },
            "task_result": {
                "agent": self.name,
                "goal": goal,
                "title": title,
                "tool": self.tool_name,
                "result_count": len(deduped_items),
            },
        }

    def _rank_results(self, raw_results: List[Dict[str, Any]], state: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
        raise NotImplementedError
