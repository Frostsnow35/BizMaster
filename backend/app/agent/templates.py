"""
@brief 一键分析模板定义层

定义预设分析场景模板，用户在对话之外可一键发起分析。
每个模板包含：id、名称、描述、分析问题、推荐角色。
"""

from typing import Any, Dict, List


TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "sales_trend",
        "name": "销售趋势",
        "description": "最近30天销售额走势与渠道拆分",
        "question": "最近30天每日销售额趋势如何？按渠道拆分",
        "role_key": "data_analyst",
    },
    {
        "id": "category_share",
        "name": "品类占比",
        "description": "各品类销售额占比与排行",
        "question": "各品类销售额占比是多少？哪个品类卖得最好？",
        "role_key": "data_analyst",
    },
    {
        "id": "customer_profile",
        "name": "客户画像",
        "description": "客户地域、客单价与购买频次分布",
        "question": "分析客户画像，包括地域分布、客单价分布、购买频次分布",
        "role_key": "operations_analyst",
    },
    {
        "id": "rfm_segmentation",
        "name": "RFM 分层",
        "description": "识别高价值客户与流失风险客户",
        "question": "对客户进行 RFM 分层，识别高价值客户和流失风险客户",
        "role_key": "operations_analyst",
    },
    {
        "id": "business_health",
        "name": "经营健康度",
        "description": "GMV、订单量、客单价、退货率等核心指标",
        "question": "评估整体经营健康度，分析 GMV、订单量、客单价、退货率等核心指标",
        "role_key": "finance_analyst",
    },
    {
        "id": "profit_margin",
        "name": "利润毛利",
        "description": "利润与毛利结构，高低毛利品类",
        "question": "分析利润与毛利情况，识别高毛利和低毛利品类",
        "role_key": "finance_analyst",
    },
    {
        "id": "channel_conversion",
        "name": "渠道转化",
        "description": "各渠道转化漏斗与瓶颈",
        "question": "分析各渠道的转化效果与漏斗，找出转化瓶颈",
        "role_key": "operations_analyst",
    },
    {
        "id": "repurchase_churn",
        "name": "复购流失",
        "description": "客户复购率与流失风险",
        "question": "分析客户复购率与流失情况，识别流失风险客户",
        "role_key": "operations_analyst",
    },
    {
        "id": "growth_opportunity",
        "name": "增长机会",
        "description": "拉新、留存、转化的增长机会点",
        "question": "从拉新、留存、转化三个维度分析增长机会点",
        "role_key": "operations_analyst",
    },
]


def get_templates() -> List[Dict[str, Any]]:
    """
    @brief 获取全部一键分析模板
    @return 模板清单列表
    """
    return TEMPLATES
