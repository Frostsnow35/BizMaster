"""
@brief 轻量级异常检测模块

在工具执行完毕后检测关键指标的异常波动，对比历史均值，
标记超过阈值的异常指标。不依赖重组件，所有异常静默捕获，
确保异常检测失败不影响主流程。
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional

from app.core.database import SessionLocal
from app.models.analysis_record import AnalysisRecord
from app.models.data_source import DataSource

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 常量定义
# ─────────────────────────────────────────────

# 金额/数值相关关键字（用于从 dict 输出中识别指标字段）
_VALUE_KEYWORDS = [
    "total", "amount", "value", "gmv", "revenue", "sum",
    "销售额", "金额", "GMV", "营收", "收入", "总计", "合计", "总量",
    "profit", "利润", "cost", "成本", "sales", "订单",
]

# 指标名 → 人类可读显示名
_METRIC_DISPLAY_MAP = {
    "gmv": "GMV",
    "revenue": "营收",
    "amount": "金额",
    "total": "总计",
    "value": "数值",
    "sum": "合计",
    "sales": "销售额",
    "profit": "利润",
    "cost": "成本",
    "销售额": "销售额",
    "GMV": "GMV",
    "营收": "营收",
    "金额": "金额",
    "总计": "总计",
    "合计": "合计",
    "收入": "收入",
    "利润": "利润",
    "成本": "成本",
    "订单": "订单数",
}

# 聚合方法 → 中文后缀
_METHOD_LABELS = {
    "sum": "合计",
    "mean": "均值",
    "avg": "均值",
    "max": "最大值",
    "min": "最小值",
    "count": "计数",
    "median": "中位数",
}

# 异常可能原因（按方向）
_CAUSES_UP = [
    "季节性需求增长",
    "促销活动推动",
    "新品上市带动销量",
    "渠道拓展效果显现",
]

_CAUSES_DOWN_GENERAL = [
    "市场需求疲软",
    "供应链问题",
    "季节性回落",
    "竞品冲击",
]

_CAUSES_DOWN_GMV = [
    "商品缺货",
    "促销活动结束",
    "竞品降价活动",
    "退货率上升",
]


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def detect_anomalies(tool_results: list, data_source_id: str) -> list[dict]:
    """
    @brief 检测工具执行结果中的异常指标波动

    执行流程：
    1. 从当前 tool_results 中提取数值指标
    2. 查询历史分析记录，获取同数据源的历史均值
    3. 对比当前值与历史均值，标记超过阈值的异常项
    4. 若无历史数据或发生任何异常，静默返回空列表

    @param tool_results ToolResult 对象列表（Pydantic 模型，含 .success .output .step_id）
    @param data_source_id 当前数据源 ID
    @return 异常指标列表，格式为：
        [{
            "metric": str,        # 指标名
            "current": str,       # 当前值（格式化显示）
            "avg": str,           # 历史均值（格式化显示）
            "change_pct": float,  # 变化百分比（正数上升，负数下降）
            "direction": str,     # "上升" 或 "下降"
            "severity": str,      # "warning"（>30%）或 "info"（15%~30%）
            "possible_causes": [str, ...]  # 可能原因列表
        }, ...]
    """
    try:
        # 1. 提取当前指标
        current_metrics = _extract_metrics_from_results(tool_results)
        if not current_metrics:
            return []

        # 2. 获取历史均值
        historical_avgs = _get_historical_averages(data_source_id, current_metrics)
        if not historical_avgs:
            return []

        # 3. 对比与标记
        anomalies = _compare_and_flag(current_metrics, historical_avgs)
        return anomalies

    except Exception as e:
        logger.warning(f"异常检测失败（不影响主流程）: {e}")
        return []


# ─────────────────────────────────────────────
# 指标提取
# ─────────────────────────────────────────────

def _extract_metrics_from_results(tool_results: list) -> List[Dict[str, Any]]:
    """
    @brief 从 ToolResult 列表中提取可比较的数值指标

    遍历所有成功的 tool_result.output：
    - dict 类型：匹配金额/数值关键字字段
    - list 类型：记录行数变化
    - 跳过 None 和纯文本

    @param tool_results ToolResult 对象列表
    @return 指标列表，每项含 metric / current_value / step_id
    """
    metrics = []

    for tr in tool_results:
        try:
            if not tr.success or tr.output is None:
                continue
            output = tr.output
            step_id = getattr(tr, "step_id", 0)

            extracted = _extract_from_output(output, step_id)
            metrics.extend(extracted)
        except Exception:
            continue

    return metrics


def _extract_from_output(output: Any, step_id: int) -> List[Dict[str, Any]]:
    """
    @brief 从单个工具输出中提取指标
    @param output 工具输出（dict / list / 其他）
    @param step_id 步骤 ID
    @return 提取到的指标列表
    """
    results = []

    if isinstance(output, dict):
        results.extend(_extract_from_dict(output, step_id))
    elif isinstance(output, list):
        results.extend(_extract_from_list(output, step_id))
    elif isinstance(output, str):
        results.extend(_extract_from_text(output, step_id))

    return results


def _extract_from_dict(output: dict, step_id: int) -> List[Dict[str, Any]]:
    """
    @brief 从 dict 类型的输出中提取指标

    覆盖场景：
    - 扁平 dict 中含 value/amount/total 等字段
    - statistics 工具的输出：{"type": "scalar", "column": "...", "method": "sum", "value": 123}
    - statistics 工具的输出：{"type": "multi_column", "method": "sum", "data": {"col1": 1, "col2": 2}}
    - data_query 工具的输出：{"columns": [...], "data": [...], "row_count": N}
    - statistics compare 输出：{"type": "compare", "current_value": ...}
    - 嵌套 dict（递归一层）

    @param output dict 类型输出
    @param step_id 步骤 ID
    @return 指标列表
    """
    results = []

    # ── 场景1：statistics scalar 输出 ──
    if output.get("type") == "scalar" and "value" in output:
        value = output["value"]
        if isinstance(value, (int, float)):
            col = output.get("column", "")
            method = output.get("method", "sum")
            method_label = _METHOD_LABELS.get(method, "")
            metric_name = _build_metric_name(col, method_label)
            results.append({
                "metric": metric_name,
                "current_value": float(value),
                "step_id": step_id,
            })

    # ── 场景2：statistics multi_column 输出 ──
    if output.get("type") == "multi_column" and "data" in output:
        data = output["data"]
        method = output.get("method", "sum")
        method_label = _METHOD_LABELS.get(method, "")
        if isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, (int, float)):
                    metric_name = _build_metric_name(str(key), method_label)
                    results.append({
                        "metric": metric_name,
                        "current_value": float(val),
                        "step_id": step_id,
                    })

    # ── 场景3：statistics compare 输出 ──
    if output.get("type") == "compare" and "current_value" in output:
        cv = output.get("current_value")
        if isinstance(cv, (int, float)):
            col = output.get("column", "指标")
            results.append({
                "metric": _build_metric_name(str(col), "合计"),
                "current_value": float(cv),
                "step_id": step_id,
            })

    # ── 场景4：data_query 输出，提取 row_count ──
    if "row_count" in output and isinstance(output.get("row_count"), (int, float)):
        results.append({
            "metric": "结果行数",
            "current_value": float(output["row_count"]),
            "step_id": step_id,
        })

    # ── 场景5：data_query grouped_aggregate 输出，提取聚合值列 ──
    if output.get("type") == "grouped_aggregate" and "data" in output:
        data = output["data"]
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            group_column = output.get("group_column", "")
            sample_row = data[0]
            for key, val in sample_row.items():
                if key == group_column:
                    continue
                if isinstance(val, (int, float)):
                    total_val = sum(
                        r.get(key, 0) for r in data
                        if isinstance(r.get(key), (int, float))
                    )
                    results.append({
                        "metric": _build_metric_name(str(key), "合计"),
                        "current_value": float(total_val),
                        "step_id": step_id,
                    })

    # ── 场景6：扁平 dict 中的数值字段 ──
    for key, val in output.items():
        key_lower = str(key).lower()
        if isinstance(val, (int, float)) and not key_lower.startswith("_"):
            if _matches_value_keyword(key_lower):
                metric_name = _resolve_display_name(str(key))
                if not any(m["metric"] == metric_name and m["step_id"] == step_id for m in results):
                    results.append({
                        "metric": metric_name,
                        "current_value": float(val),
                        "step_id": step_id,
                    })

    # ── 场景7：递归处理嵌套 dict（仅一层，避免深度递归） ──
    for key, val in output.items():
        if isinstance(val, dict) and key not in ("statistics", "data"):
            try:
                sub_results = _extract_from_dict(val, step_id)
                for sr in sub_results:
                    if not any(
                        m["metric"] == sr["metric"] and m["step_id"] == step_id
                        for m in results
                    ):
                        results.append(sr)
            except Exception:
                continue

    # 去重：同名指标 + 同 step_id 只保留一个
    deduped = {}
    for r in results:
        dedup_key = (r["metric"], r["step_id"])
        deduped[dedup_key] = r
    return list(deduped.values())


def _extract_from_list(output: list, step_id: int) -> List[Dict[str, Any]]:
    """
    @brief 从 list 类型输出中提取指标（记录行数变化）

    @param output list 类型输出
    @param step_id 步骤 ID
    @return 指标列表
    """
    return [{
        "metric": "数据行数",
        "current_value": float(len(output)),
        "step_id": step_id,
    }]


def _extract_from_text(output: str, step_id: int) -> List[Dict[str, Any]]:
    """
    @brief 从文本输出中尝试提取数值指标

    匹配模式如 "GMV ¥142,300"、"销售额 142300 元" 等。

    @param output 文本输出
    @param step_id 步骤 ID
    @return 指标列表
    """
    results = []

    for kw in ["GMV", "gmv", "销售额", "营收", "收入", "金额", "利润", "成本"]:
        pattern = rf"{re.escape(kw)}[^\d]*?¥?\s*([\d,]+(?:\.\d+)?)\s*(?:元|万|亿)?"
        matches = re.findall(pattern, output, re.IGNORECASE)
        for m in matches:
            try:
                val = float(m.replace(",", ""))
                results.append({
                    "metric": _resolve_display_name(kw),
                    "current_value": val,
                    "step_id": step_id,
                })
            except (ValueError, TypeError):
                continue

    return results


# ─────────────────────────────────────────────
# 历史均值查询
# ─────────────────────────────────────────────

def _get_historical_averages(
    data_source_id: str,
    current_metrics: List[Dict[str, Any]],
) -> Dict[str, float]:
    """
    @brief 从历史分析记录中获取同数据源的历史均值

    策略：
    1. 通过 data_source_id 查 data_sources 表获取数据源名称
    2. 查询 analysis_records 中所有 done 事件
    3. 解析每条 done 事件的 content JSON，提取 final_response 文本
    4. 尝试从 final_response 中提取与当前指标同名的数值
    5. 汇总计算各指标的算术均值

    @param data_source_id 当前数据源 ID
    @param current_metrics 当前提取到的指标列表
    @return {metric_name: avg_value} 字典，无法获取时返回空 dict
    """
    db = None
    try:
        db = SessionLocal()

        # 获取数据源名称，用于过滤历史记录
        source = db.query(DataSource).filter(DataSource.id == data_source_id).first()
        source_name = source.name if source else ""

        # 查询所有 done 事件，按时间倒序，最多取最近 50 条
        records = (
            db.query(AnalysisRecord)
            .filter(AnalysisRecord.msg_type == "done")
            .order_by(AnalysisRecord.created_at.desc())
            .limit(50)
            .all()
        )

        if not records:
            return {}

        # 按指标名收集历史数值
        history_values: Dict[str, List[float]] = {}

        for record in records:
            try:
                content = json.loads(record.content) if isinstance(record.content, str) else record.content
            except (json.JSONDecodeError, TypeError):
                continue

            final_response = content.get("final_response", "")
            data_summary = content.get("data_summary", "")

            # 通过 data_summary 中的名称判断是否同数据源
            if source_name and source_name not in data_summary and source_name not in final_response:
                continue

            # 从 final_response 文本中提取数值
            for cm in current_metrics:
                metric_name = cm["metric"]
                text_val = _extract_metric_value_from_text(final_response, metric_name)
                if text_val is not None:
                    if metric_name not in history_values:
                        history_values[metric_name] = []
                    history_values[metric_name].append(text_val)

        # 如果通过数据源名过滤获取不到，放宽过滤条件再试一次
        if not history_values:
            for record in records:
                try:
                    content = json.loads(record.content) if isinstance(record.content, str) else record.content
                except (json.JSONDecodeError, TypeError):
                    continue

                final_response = content.get("final_response", "")
                for cm in current_metrics:
                    metric_name = cm["metric"]
                    text_val = _extract_metric_value_from_text(final_response, metric_name)
                    if text_val is not None:
                        if metric_name not in history_values:
                            history_values[metric_name] = []
                        history_values[metric_name].append(text_val)

        # 计算均值
        avgs = {}
        for metric_name, values in history_values.items():
            if values:
                avgs[metric_name] = sum(values) / len(values)

        return avgs

    except Exception:
        return {}
    finally:
        if db:
            try:
                db.close()
            except Exception:
                pass


def _extract_metric_value_from_text(text: str, metric_name: str) -> Optional[float]:
    """
    @brief 从文本中尝试提取指定指标的数值

    匹配模式：
    - 「GMV ¥142,300」
    - 「销售额达到 14.23 万元」
    - 「GMV: 142,300」
    - 「总销售额 500000」

    @param text 文本内容
    @param metric_name 指标名（如 "GMV"、"销售额合计"）
    @return 数值，无法提取时返回 None
    """
    if not text or not metric_name:
        return None

    search_terms = [metric_name]

    # 去掉 "合计"、"均值" 等后缀作为独立搜索词
    clean_name = metric_name
    for suffix in ["合计", "均值", "最大值", "最小值", "中位数", "计数"]:
        if clean_name.endswith(suffix):
            clean_name = clean_name[:-len(suffix)]
            break
    if clean_name and clean_name != metric_name:
        search_terms.append(clean_name)

    for term in search_terms:
        # 允许指标名和数字之间有任意分隔符
        pattern = rf"{re.escape(term)}[^\d\n]*?(\d[\d,]*\.?\d*)"
        matches = re.findall(pattern, text, re.IGNORECASE)

        for m in matches:
            try:
                val = float(m.replace(",", ""))
                # 检查是否有"万"/"亿"单位
                context_start = max(0, text.lower().find(m.lower()) - 5)
                context_end = min(len(text), text.lower().find(m.lower()) + len(m) + 5)
                context = text[context_start:context_end].lower()

                if "亿" in context:
                    val *= 100000000
                elif "万" in context:
                    val *= 10000
                elif "k" in context:
                    val *= 1000

                if val > 0:
                    return val
            except (ValueError, TypeError):
                continue

    return None


# ─────────────────────────────────────────────
# 对比与标记
# ─────────────────────────────────────────────

def _compare_and_flag(
    current_metrics: List[Dict[str, Any]],
    historical_avgs: Dict[str, float],
) -> List[Dict[str, Any]]:
    """
    @brief 对比当前指标与历史均值，标记异常

    阈值规则：
    - |change_pct| > 30  → severity: "warning"
    - 15 < |change_pct| <= 30 → severity: "info"
    - |change_pct| <= 15 → 不标记（跳过）

    @param current_metrics 当前指标列表
    @param historical_avgs 历史均值字典
    @return 异常项列表
    """
    anomalies = []

    for cm in current_metrics:
        metric_name = cm["metric"]
        current_value = cm["current_value"]

        # 查找历史均值（精确匹配 → 模糊匹配）
        avg_value = historical_avgs.get(metric_name)
        if avg_value is None:
            avg_value = _fuzzy_match_avg(metric_name, historical_avgs)

        if avg_value is None or avg_value == 0:
            continue

        # 计算变化百分比
        change_pct = round((current_value - avg_value) / avg_value * 100, 1)

        # 阈值判定
        abs_change = abs(change_pct)
        if abs_change <= 15:
            continue

        severity = "warning" if abs_change > 30 else "info"
        direction = "上升" if change_pct > 0 else "下降"

        # 格式化显示值
        current_display = _format_value(current_value)
        avg_display = _format_value(avg_value)

        # 可能原因
        possible_causes = _get_possible_causes(metric_name, direction)

        anomalies.append({
            "metric": metric_name,
            "current": current_display,
            "avg": avg_display,
            "change_pct": change_pct,
            "direction": direction,
            "severity": severity,
            "possible_causes": possible_causes,
        })

    return anomalies


def _fuzzy_match_avg(
    metric_name: str,
    historical_avgs: Dict[str, float],
) -> Optional[float]:
    """
    @brief 模糊匹配历史均值

    当精确匹配失败时，尝试：
    1. 指标名去掉后缀后匹配（如 "销售额合计" → "销售额"）
    2. 子串包含匹配

    @param metric_name 当前指标名
    @param historical_avgs 历史均值字典
    @return 匹配到的历史均值，无匹配则返回 None
    """
    clean = metric_name
    for suffix in ["合计", "均值", "最大值", "最小值", "中位数", "计数"]:
        if clean.endswith(suffix):
            clean = clean[:-len(suffix)]
            if clean in historical_avgs:
                return historical_avgs[clean]
            break

    for hist_key, hist_val in historical_avgs.items():
        if clean.lower() in hist_key.lower() or hist_key.lower() in clean.lower():
            return hist_val

    return None


# ─────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────

def _matches_value_keyword(key: str) -> bool:
    """
    @brief 检查字段名是否匹配金额/数值关键字
    @param key 字段名（小写）
    @return 是否匹配
    """
    key_lower = key.lower().strip()
    for kw in _VALUE_KEYWORDS:
        if kw.lower() in key_lower:
            return True
    return False


def _resolve_display_name(raw_key: str) -> str:
    """
    @brief 将原始字段名解析为人类可读的指标名
    @param raw_key 原始字段名
    @return 显示名
    """
    key_lower = raw_key.lower().strip()
    for kw, display in _METRIC_DISPLAY_MAP.items():
        if kw.lower() in key_lower:
            return display
    return raw_key


def _build_metric_name(column_name: str, method_label: str) -> str:
    """
    @brief 构建指标名：「列名 + 方法后缀」

    @param column_name 列名
    @param method_label 聚合方法的中文标签（如 "合计"、"均值"）
    @return 指标名（如 "GMV合计"、"销售额均值"）
    """
    display_col = _resolve_display_name(column_name)
    if method_label and method_label not in display_col:
        return f"{display_col}{method_label}"
    return display_col


def _format_value(value: float) -> str:
    """
    @brief 格式化数值为人类可读字符串

    规则：
    - >= 1亿 → "¥X.XX亿"
    - >= 1万 → "¥X.XX万"
    - 其他 → "¥X,XXX"

    @param value 数值
    @return 格式化字符串
    """
    if value >= 100000000:
        return f"¥{value / 100000000:.2f}亿"
    if value >= 10000:
        return f"¥{value / 10000:.2f}万"
    return f"¥{value:,.0f}"


def _get_possible_causes(metric_name: str, direction: str) -> List[str]:
    """
    @brief 根据指标名和变化方向，返回可能原因列表

    @param metric_name 指标名
    @param direction "上升" 或 "下降"
    @return 可能原因列表
    """
    if direction == "上升":
        return list(_CAUSES_UP)

    metric_lower = metric_name.lower()
    if any(kw in metric_lower for kw in ["gmv", "销售额", "营收", "收入"]):
        return list(_CAUSES_DOWN_GMV)

    return list(_CAUSES_DOWN_GENERAL)
