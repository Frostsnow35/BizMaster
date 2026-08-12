"""
@brief 文件解析器模块

支持自动检测 CSV/Excel 格式，编码自动识别，统一解析为 pandas DataFrame。
"""
import os
from io import BytesIO
from typing import Tuple, List, Dict, Any

import pandas as pd
import chardet


def detect_format(filename: str) -> str:
    """
    @brief 根据文件扩展名检测文件格式
    @param filename 文件名
    @return "csv" | "excel"
    @throws ValueError 格式不支持时抛出
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".csv":
        return "csv"
    elif ext in (".xlsx", ".xls"):
        return "excel"
    else:
        raise ValueError(f"不支持的文件格式: {ext}，仅支持 CSV 和 Excel 格式")


def _detect_encoding(file_content: bytes) -> str:
    """
    @brief 检测文件编码
    @param file_content 文件二进制内容
    @return 编码名称（如 "utf-8", "gbk"）
    """
    result = chardet.detect(file_content)
    encoding = result.get("encoding", "utf-8")
    confidence = result.get("confidence", 0)

    # 低置信度时回退到常见中文编码
    if confidence < 0.7:
        for enc in ["utf-8", "gbk", "gb2312", "gb18030"]:
            try:
                file_content.decode(enc)
                return enc
            except (UnicodeDecodeError, LookupError):
                continue
    return encoding or "utf-8"


def parse_csv(file_content: bytes, filename: str) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    @brief 解析 CSV 文件为 DataFrame
    @param file_content 文件二进制内容
    @param filename 文件名（用于日志）
    @return (DataFrame, columns_info 列表)
    """
    encoding = _detect_encoding(file_content)
    text = file_content.decode(encoding, errors="replace")

    df = pd.read_csv(BytesIO(text.encode("utf-8")), encoding="utf-8")

    columns_info = _build_columns_info(df)
    return df, columns_info


def parse_excel(file_content: bytes, filename: str) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    @brief 解析 Excel 文件为 DataFrame（默认读取第一个 sheet）
    @param file_content 文件二进制内容
    @param filename 文件名
    @return (DataFrame, columns_info 列表)
    """
    df = pd.read_excel(BytesIO(file_content), sheet_name=0, engine="openpyxl")
    columns_info = _build_columns_info(df)
    return df, columns_info


def parse_file(file_content: bytes, filename: str) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    @brief 统一文件解析入口，自动检测格式
    @param file_content 文件二进制内容
    @param filename 文件名
    @return (DataFrame, columns_info 列表)
    @throws ValueError 格式不支持时抛出
    """
    fmt = detect_format(filename)
    if fmt == "csv":
        return parse_csv(file_content, filename)
    else:
        return parse_excel(file_content, filename)


def _build_columns_info(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    @brief 构建列元信息列表
    @param df DataFrame
    @return [{"name": str, "dtype": str, "null_count": int, "null_ratio": float}, ...]
    """
    columns_info = []
    for col in df.columns:
        col_name = str(col)
        dtype = str(df[col].dtype)
        null_count = int(df[col].isnull().sum())
        total = len(df)
        null_ratio = round(null_count / total, 4) if total > 0 else 0.0
        columns_info.append({
            "name": col_name,
            "dtype": dtype,
            "null_count": null_count,
            "null_ratio": null_ratio,
        })
    return columns_info


# ─────────────────────────────────────────────
# 平台模板定义与匹配
# ─────────────────────────────────────────────

# 平台模板：每个平台定义一组关键列名特征（关键字列表）
# 匹配时计算数据源列名与模板特征的交集比例作为得分
PLATFORM_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "taobao": {
        "name": "淘宝",
        "key_columns": ["订单编号", "买家会员名", "应付金额", "实付金额", "商品标题", "商品数量"],
        "column_mapping": {
            "订单编号": "order_id",
            "买家会员名": "customer_name",
            "买家支付宝账号": "customer_account",
            "应付金额": "amount",
            "实付金额": "paid_amount",
            "商品标题": "product_name",
            "商品数量": "quantity",
            "订单状态": "order_status",
            "收货人姓名": "receiver_name",
            "收货地址": "receiver_address",
            "联系手机": "contact_phone",
            "订单创建时间": "order_time",
            "订单付款时间": "payment_time",
        },
    },
    "pinduoduo": {
        "name": "拼多多",
        "key_columns": ["订单号", "商品金额", "成交时间", "商品名称", "商品数量"],
        "column_mapping": {
            "订单号": "order_id",
            "商品金额": "amount",
            "成交时间": "order_time",
            "商品名称": "product_name",
            "商品数量": "quantity",
            "买家昵称": "customer_name",
            "收货人": "receiver_name",
            "收货地址": "receiver_address",
            "手机号": "contact_phone",
            "订单状态": "order_status",
            "支付金额": "paid_amount",
        },
    },
    "douyin": {
        "name": "抖音",
        "key_columns": ["订单ID", "商品单价", "下单时间", "商品名称", "购买数量", "实付金额"],
        "column_mapping": {
            "订单ID": "order_id",
            "商品单价": "unit_price",
            "下单时间": "order_time",
            "商品名称": "product_name",
            "购买数量": "quantity",
            "实付金额": "paid_amount",
            "收货人": "receiver_name",
            "收货地址": "receiver_address",
            "联系电话": "contact_phone",
            "买家昵称": "customer_name",
            "订单状态": "order_status",
        },
    },
    "jd": {
        "name": "京东",
        "key_columns": ["订单编号", "商品总额", "下单时间", "商品名称", "商品数量"],
        "column_mapping": {
            "订单编号": "order_id",
            "商品总额": "amount",
            "下单时间": "order_time",
            "商品名称": "product_name",
            "商品数量": "quantity",
            "收货人姓名": "receiver_name",
            "收货地址": "receiver_address",
            "手机号": "contact_phone",
            "客户姓名": "customer_name",
            "实际支付": "paid_amount",
            "订单状态": "order_status",
        },
    },
}

# 最小匹配得分阈值（低于此值视为通用数据源）
_MIN_PLATFORM_SCORE = 0.3


def match_platform(df: pd.DataFrame) -> Dict[str, Any]:
    """
    @brief 根据 DataFrame 列名匹配数据来源平台模板
    @param df pandas DataFrame
    @return {
        "platform": str,       # 平台标识: taobao/pinduoduo/douyin/jd/generic
        "platform_name": str,  # 平台中文名
        "score": float,        # 匹配得分 (0.0~1.0)
        "column_mapping": dict,  # 命中的列名映射 {原始列名: 标准列名}
    }
    """
    col_set = {str(c).strip() for c in df.columns}

    best_platform = "generic"
    best_name = "通用"
    best_score = 0.0
    best_mapping: Dict[str, str] = {}

    for pkey, template in PLATFORM_TEMPLATES.items():
        key_cols = template["key_columns"]
        full_mapping = template["column_mapping"]

        # 计算交集得分
        matched_keys = [k for k in key_cols if _fuzzy_in(k, col_set)]
        score = len(matched_keys) / len(key_cols) if key_cols else 0

        # 构建列名映射（只包含命中的列）
        mapping: Dict[str, str] = {}
        for orig_col in col_set:
            # 精确匹配优先
            if orig_col in full_mapping:
                mapping[orig_col] = full_mapping[orig_col]
            else:
                # 模糊匹配（子串匹配）
                for template_col, std_col in full_mapping.items():
                    if template_col in orig_col or orig_col in template_col:
                        mapping[orig_col] = std_col
                        break

        if score > best_score:
            best_score = score
            best_platform = pkey
            best_name = template["name"]
            best_mapping = mapping

    if best_score < _MIN_PLATFORM_SCORE:
        return {
            "platform": "generic",
            "platform_name": "通用",
            "score": best_score,
            "column_mapping": {},
        }

    return {
        "platform": best_platform,
        "platform_name": best_name,
        "score": round(best_score, 2),
        "column_mapping": best_mapping,
    }


def _fuzzy_in(target: str, col_set: set) -> bool:
    """
    @brief 检查 target 是否模糊存在于列名集合中
    支持精确匹配和子串匹配（如"订单编号"能匹配到"淘宝订单编号"）
    """
    for col in col_set:
        if target == col or target in col or col in target:
            return True
    return False
