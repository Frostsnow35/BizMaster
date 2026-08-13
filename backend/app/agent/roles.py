"""
@brief 多角色分析师定义层

定义三个专业分析师角色：数据分析师、电商运营专家、财务经营分析师。
每个角色包含：
- persona：注入 Responder 的角色人格提示词，决定回答视角与措辞
- planner_hint：注入 Planner 的规划提示词，决定优先拆解哪些指标与工具
- chart_preferences：该角色偏好的图表类型（供图表适配）
- report_structure：该角色报告结构（供专业报告）
- keywords：用于根据问题自动推断角色的关键词
"""

from typing import Any, Dict, Optional


ROLES: Dict[str, Dict[str, Any]] = {
    "data_analyst": {
        "key": "data_analyst",
        "name": "数据分析师",
        "description": "统计指标、趋势、异常与归因",
        "persona": (
            "你是一名专业的数据分析师。请从统计与数据的角度解读结果，"
            "重点呈现指标变化、时间趋势、分布结构与异常波动，并尝试归因。"
            "输出要有数据支撑，结论需落到具体的数值与幅度。"
        ),
        "planner_hint": (
            "以数据分析师视角规划：优先拆解核心指标、时间趋势、维度对比与异常检测，"
            "合理组合 data_query / statistics / ecommerce_metrics 与 visualization。"
        ),
        "chart_preferences": ["line", "bar", "pie", "scatter"],
        "report_structure": ["核心指标概览", "趋势与分布", "异常与归因", "行动建议"],
        "keywords": ["趋势", "统计", "分布", "对比", "排行", "占比", "分析", "概览", "异常", "波动"],
    },
    "operations_analyst": {
        "key": "operations_analyst",
        "name": "电商运营专家",
        "description": "客户分层、复购流失、渠道转化与增长",
        "persona": (
            "你是一名电商运营专家。请从精细化运营与增长的角度解读数据，"
            "重点回答客户是谁、复购与流失情况、哪个渠道有效、转化漏斗卡在哪里，"
            "并结合 RFM 分层、渠道效果与获客成本给出可落地的运营策略与预算建议。"
        ),
        "planner_hint": (
            "以电商运营专家视角规划：优先分析客户画像、RFM 分层、复购与流失、渠道效果与转化漏斗，"
            "优先使用 ecommerce_metrics 中的 rfm / repeat_purchase_rate / ltv / cac / roas，"
            "并配合 funnel、radar 等运营类图表。"
        ),
        "chart_preferences": ["funnel", "bar", "line", "pie", "radar"],
        "report_structure": ["运营总览", "客户与复购", "渠道与转化", "增长建议"],
        "keywords": [
            "客户", "用户", "会员", "复购", "流失", "画像", "分层", "RFM", "留存", "忠诚",
            "新客", "老客", "回头客", "渠道", "转化", "漏斗", "拉新", "增长", "营销",
            "推广", "广告", "活动", "曝光", "点击", "投放", "获客", "运营", "选品", "爆款",
        ],
    },
    "finance_analyst": {
        "key": "finance_analyst",
        "name": "财务经营分析师",
        "description": "利润、成本、毛利、ROI、库存周转",
        "persona": (
            "你是一名财务经营分析师。请从盈利性、成本结构与资金效率的视角解读数据，"
            "重点回答赚不赚钱、成本是否可控、哪些环节在消耗利润、如何提升投入产出比。"
            "尽量落到毛利率、ROI、库存周转率等经营指标。"
        ),
        "planner_hint": (
            "以财务经营分析师视角规划：优先计算利润、成本、毛利率、ROI、库存周转等指标，"
            "优先使用 ecommerce_metrics 工具，并补充明细佐证。"
        ),
        "chart_preferences": ["indicator", "bar", "waterfall"],
        "report_structure": ["经营健康度", "盈利与成本", "资金与库存效率", "改善建议"],
        "keywords": ["利润", "成本", "毛利", "毛利率", "ROI", "投入产出", "库存", "周转", "盈亏", "费用", "现金流", "赚", "净利"],
    },
}

# 归一化角色键（auto 表示由角色路由自动推断）
AUTO_ROLE_KEY = "auto"
DEFAULT_ROLE_KEY = "data_analyst"


def get_role(role_key: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    @brief 获取角色定义
    @param role_key 角色键（data_analyst / operations_analyst / finance_analyst）
    @return 角色定义字典，未知或空键返回 None
    """
    if not role_key:
        return None
    return ROLES.get(role_key)


def infer_role(question: str) -> str:
    """
    @brief 根据问题关键词自动推断分析角色
    @param question 用户问题
    @return 归一化角色键，默认 data_analyst
    """
    if not question:
        return DEFAULT_ROLE_KEY

    text = question.lower()
    best_key = DEFAULT_ROLE_KEY
    best_score = 0
    for key, role in ROLES.items():
        score = sum(1 for kw in role["keywords"] if kw.lower() in text)
        if score > best_score:
            best_score = score
            best_key = key
    return best_key


def resolve_role_key(role_key: Optional[str], question: str) -> str:
    """
    @brief 归一化角色键：auto / 空值通过 infer_role 推断，其余直接返回
    @param role_key 用户传入的角色键
    @param question 用户问题（推断时需要）
    @return 最终角色键
    """
    if not role_key or role_key == AUTO_ROLE_KEY:
        return infer_role(question)
    return role_key if role_key in ROLES else DEFAULT_ROLE_KEY
