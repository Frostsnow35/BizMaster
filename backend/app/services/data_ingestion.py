"""
@brief 数据接入服务模块

负责将解析后的 DataFrame 写入 SQLite，管理数据源生命周期。
"""

import uuid
import datetime
import time
from typing import Dict, Any, Optional
from sqlalchemy import inspect, text
import pandas as pd

from app.core.database import engine, SessionLocal
from app.models.data_source import DataSource


# ── DataFrame 缓存 ──
# 缓存结构: {data_source_id: (timestamp, DataFrame)}
# TTL = 60 秒，最多 5 个条目
_df_cache: Dict[str, tuple[float, pd.DataFrame]] = {}
_CACHE_TTL = 60
_CACHE_MAX_SIZE = 5


def _cache_get(data_source_id: str) -> Optional[pd.DataFrame]:
    """从缓存获取 DataFrame，过期返回 None"""
    entry = _df_cache.get(data_source_id)
    if entry is None:
        return None
    ts, df = entry
    if time.time() - ts > _CACHE_TTL:
        del _df_cache[data_source_id]
        return None
    return df


def _cache_set(data_source_id: str, df: pd.DataFrame) -> None:
    """将 DataFrame 放入缓存，超出容量时淘汰最旧条目"""
    if len(_df_cache) >= _CACHE_MAX_SIZE:
        oldest_key = min(_df_cache, key=lambda k: _df_cache[k][0])
        del _df_cache[oldest_key]
    _df_cache[data_source_id] = (time.time(), df)


def _cache_invalidate(data_source_id: str) -> None:
    """清除指定数据源的缓存"""
    _df_cache.pop(data_source_id, None)


def generate_table_name(name: str) -> str:
    """
    @brief 生成唯一 SQLite 表名
    @param name 数据源原始名称
    @return 唯一表名（格式: ds_shortuuid）
    """
    short_id = str(uuid.uuid4())[:8]
    return f"ds_{short_id}"


def ingest_dataframe(
    df: pd.DataFrame,
    name: str,
    file_path: Optional[str] = None,
    file_type: Optional[str] = None,
    file_size_kb: Optional[int] = None,
    mode: str = "replace",
    columns_meta: Optional[list] = None,
    platform: Optional[str] = None,
    column_mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    @brief 将 DataFrame 写入 SQLite 并创建数据源记录
    @param df 待写入的 DataFrame
    @param name 数据源名称
    @param file_path 原始文件路径（可选）
    @param file_type 文件类型 (csv/xlsx)
    @param file_size_kb 文件大小(KB)
    @param mode "replace" 覆盖 或 "append" 追加
    @param columns_meta 列元信息（可选，不传则自动构建）
    @param platform 数据来源平台标识（可选）
    @param column_mapping 列名映射（可选）
    @return {"data_source_id": str, "table_name": str, "row_count": int, "columns_meta": list}
    """
    table_name = generate_table_name(name)
    row_count = len(df)

    # 写入 SQLite
    df.to_sql(
        name=table_name,
        con=engine,
        if_exists=mode,
        index=False,
    )

    # 构建列元信息
    if columns_meta is None:
        columns_meta = _build_columns_meta(df)

    # 推断数据源用途
    purpose = infer_purpose(name, columns_meta)

    # 创建数据源记录
    db = SessionLocal()
    try:
        data_source = DataSource(
            name=name,
            file_path=file_path,
            file_type=file_type,
            file_size_kb=file_size_kb,
            table_name=table_name,
            row_count=row_count,
            columns_meta=columns_meta,
            purpose=purpose,
            platform=platform,
            column_mapping=column_mapping,
        )
        db.add(data_source)
        db.commit()
        db.refresh(data_source)

        result = {
            "data_source_id": data_source.id,
            "table_name": table_name,
            "row_count": row_count,
            "columns_meta": columns_meta,
        }
        return result
    finally:
        db.close()


def append_to_datasource(
    data_source_id: str,
    df: pd.DataFrame,
) -> Dict[str, Any]:
    """
    @brief 向已有数据源追加数据
    @param data_source_id 数据源 ID
    @param df 追加的 DataFrame
    @return 更新后的数据源信息
    @throws ValueError 如果数据源不存在
    """
    db = SessionLocal()
    try:
        data_source = db.query(DataSource).filter(DataSource.id == data_source_id).first()
        if data_source is None:
            raise ValueError(f"数据源不存在: {data_source_id}")

        # 追加到 SQLite 表
        df.to_sql(
            name=data_source.table_name,
            con=engine,
            if_exists="append",
            index=False,
        )

        # 更新行数和元信息
        data_source.row_count += len(df)
        data_source.columns_meta = _build_columns_meta(pd.read_sql_table(data_source.table_name, con=engine))
        data_source.updated_at = datetime.datetime.now()
        db.commit()

        # 清除缓存（数据已变更）
        _cache_invalidate(data_source_id)

        return data_source.to_dict()
    finally:
        db.close()


def read_datasource(data_source_id: str) -> pd.DataFrame:
    """
    @brief 从 SQLite 读取数据源为 DataFrame（优先查缓存）
    @param data_source_id 数据源 ID
    @return DataFrame
    @throws ValueError 如果数据源不存在
    """
    # 优先从缓存读取
    cached = _cache_get(data_source_id)
    if cached is not None:
        return cached.copy()

    db = SessionLocal()
    try:
        data_source = db.query(DataSource).filter(DataSource.id == data_source_id).first()
        if data_source is None:
            raise ValueError(f"数据源不存在: {data_source_id}")
        df = pd.read_sql_table(data_source.table_name, con=engine)
        _cache_set(data_source_id, df)
        return df
    finally:
        db.close()


def get_preview(data_source_id: str, limit: int = 3) -> list[dict]:
    """
    @brief 获取数据源预览（前 N 行）
    @param data_source_id 数据源 ID
    @param limit 返回行数，默认3
    @return 字典列表，每行为一个 dict
    """
    try:
        df = read_datasource(data_source_id)
        return df.head(limit).to_dict(orient="records")
    except Exception:
        return []


def delete_datasource(data_source_id: str) -> None:
    """
    @brief 删除数据源（SQLite 表 + ORM 记录）
    @param data_source_id 数据源 ID
    @throws ValueError 如果数据源不存在
    """
    db = SessionLocal()
    try:
        data_source = db.query(DataSource).filter(DataSource.id == data_source_id).first()
        if data_source is None:
            raise ValueError(f"数据源不存在: {data_source_id}")

        table_name = data_source.table_name

        # 删除 SQLite 表
        inspector = inspect(engine)
        if table_name in inspector.get_table_names():
            with engine.connect() as conn:
                conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
                conn.commit()

        # 删除 ORM 记录
        db.delete(data_source)
        db.commit()

        # 清除缓存
        _cache_invalidate(data_source_id)
    finally:
        db.close()


def _build_columns_meta(df: pd.DataFrame) -> list:
    """
    @brief 构建列元信息列表
    @param df DataFrame
    @return [{"name": str, "dtype": str, "null_count": int}, ...]
    """
    columns_meta = []
    for col in df.columns:
        columns_meta.append({
            "name": str(col),
            "dtype": str(df[col].dtype),
            "null_count": int(df[col].isnull().sum()),
        })
    return columns_meta


# 推断优先级（列名统计并列时使用）：订单 > 客户 > 库存 > 商品
_PURPOSE_PRIORITY = {
    "订单/销售数据": 4,
    "客户信息数据": 3,
    "库存数据": 2,
    "商品信息数据": 1,
}

_ORDER_KEYS = (
    "order", "订单", "销售", "交易", "下单", "支付", "实付",
    "渠道", "客单", "amount", "payment", "sale", "shop",
)
_CUSTOMER_KEYS = (
    "customer", "客户", "会员", "user", "用户", "复购", "profile",
)
_PRODUCT_KEYS = (
    "product", "商品", "sku", "类目", "品类", "货品",
)
_INVENTORY_KEYS = (
    "inventory", "库存", "stock", "warehouse", "仓",
)


def _match_count(keys: tuple, text: str) -> int:
    """统计文本中命中的关键词个数"""
    return sum(1 for k in keys if k in text)


def infer_purpose(name: str, columns_meta: Optional[list] = None) -> str:
    """
    @brief 推断数据源用途（文件名 + 列名两级匹配，一次推断全局复用）

    第1层：文件名含明确关键词则直接定类（文件名可信度最高，避免客户表的
          "订单数"列把客户表误判为订单表）。
    第2层：文件名无明确意图时，统计列名命中数取最多类别，并列时按优先级。
    @param name 数据源名称（文件名）
    @param columns_meta 列元信息列表 [{"name": str, "dtype": str}, ...]
    @return 用途中文描述，如 "订单/销售数据"
    """
    name_lower = (name or "").lower()
    col_names = " ".join(
        str(c.get("name", "")) for c in (columns_meta or [])
    ).lower()

    # 第1层：文件名强意图
    for purpose, keys in (
        ("订单/销售数据", _ORDER_KEYS),
        ("客户信息数据", _CUSTOMER_KEYS),
        ("库存数据", _INVENTORY_KEYS),
        ("商品信息数据", _PRODUCT_KEYS),
    ):
        if any(k in name_lower for k in keys):
            return purpose

    # 第2层：列名统计
    scores = {
        "订单/销售数据": _match_count(_ORDER_KEYS, col_names),
        "客户信息数据": _match_count(_CUSTOMER_KEYS, col_names),
        "库存数据": _match_count(_INVENTORY_KEYS, col_names),
        "商品信息数据": _match_count(_PRODUCT_KEYS, col_names),
    }
    best = max(scores, key=lambda k: (scores[k], _PURPOSE_PRIORITY.get(k, 0)))
    if scores[best] > 0:
        return best
    return "通用数据"
