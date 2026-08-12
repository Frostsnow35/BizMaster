"""
@brief 文件上传 API

POST /api/upload — 接收 CSV/Excel 文件，解析、校验、入库全链路。
POST /api/sample-data — 加载内置示例数据供新用户快速体验。
"""

import os
import sys
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from app.core.database import SessionLocal
from app.models.data_source import DataSource
from app.core.config import config
from app.utils.file_parser import parse_file, match_platform
from app.utils.data_validator import validate_data
from app.services.data_ingestion import ingest_dataframe

router = APIRouter(prefix="/api", tags=["upload"])


# ── 内置示例数据文件列表 ──
_SAMPLE_FILES = [
    {
        "key": "orders",
        "name": "orders.csv",
        "description": "订单数据（含销售额、品类、渠道、地区）",
    },
    {
        "key": "customers",
        "name": "customers.csv",
        "description": "客户数据（含注册时间、等级、消费金额）",
    },
]


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    mode: str = Query("check", description="上传模式: check(检查重复) / replace(覆盖) / new(新建)"),
):
    """
    @brief 上传 CSV/Excel 文件并入库
    @param file 上传的文件对象
    @param mode 处理模式
      - check: 检查重复，返回 {is_duplicate: bool, existing: DataSource}
      - replace: 覆盖已有数据（需 mode=check 返回 is_duplicate=true）
      - new: 新建数据源（同名时自动追加编号）
    @return {
        "data_source_id": str,
        "name": str,
        "table_name": str,
        "row_count": int,
        "columns_meta": list,
        "file_type": str,
        "file_size_kb": int,
        "validation_report": dict,
        "is_duplicate": bool (仅 mode=check 时),
        "existing": dict (仅 mode=check 存在重复时),
    }
    """
    # 1. 校验文件扩展名
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    ext = os.path.splitext(file.filename)[1].lower()
    file_type = ext.lstrip(".")
    allowed = config.upload.allowed_extensions
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，仅支持: {', '.join(allowed)}",
        )

    # 2. 读取内容 + 校验文件大小
    content = await file.read()
    max_size_bytes = config.upload.max_file_size_mb * 1024 * 1024
    if len(content) > max_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制（最大 {config.upload.max_file_size_mb}MB）",
        )
    file_size_kb = len(content) // 1024

    # 3. 解析文件
    try:
        df, columns_info = parse_file(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")

    if df.empty:
        raise HTTPException(status_code=400, detail="文件内容为空，请检查文件")

    # 3.5 平台模板匹配
    platform_result = match_platform(df)

    # 4. 基本名称
    base_name = os.path.splitext(file.filename)[0]

    # 5. mode=check: 查重
    db = SessionLocal()
    try:
        existing = db.query(DataSource).filter(DataSource.name == base_name).first()
    finally:
        db.close()

    if mode == "check":
        if existing:
            return {
                "is_duplicate": True,
                "existing": existing.to_dict(),
            }
        return {
            "is_duplicate": False,
            "row_count": len(df),
            "columns_meta": columns_info,
            "platform": platform_result,
        }

    # 6. 处理重复
    if existing:
        if mode == "replace":
            from app.services.data_ingestion import delete_datasource
            delete_datasource(existing.id)
        elif mode == "new":
            # 自动追加编号
            db = SessionLocal()
            try:
                count = db.query(DataSource).filter(DataSource.name.like(f"{base_name}(%)")).count()
            finally:
                db.close()
            base_name = f"{base_name}({count + 1})"
        else:
            raise HTTPException(status_code=400, detail=f"文件 '{base_name}' 已存在，请选择覆盖或新建")

    # 7. 数据校验
    try:
        validation_report = validate_data(df)
    except Exception as e:
        validation_report = {"error": str(e), "overall_score": 0}

    # 8. 入库
    try:
        result = ingest_dataframe(
            df=df,
            name=base_name,
            file_path=file.filename,
            file_type=file_type,
            file_size_kb=file_size_kb,
            mode="replace",
            columns_meta=columns_info,
            platform=platform_result["platform"],
            column_mapping=platform_result["column_mapping"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据入库失败: {str(e)}")

    return {
        **result,
        "name": base_name,
        "file_type": file_type,
        "file_size_kb": file_size_kb,
        "validation_report": validation_report,
        "platform": platform_result,
    }


@router.post("/sample-data")
async def load_sample_data(sample_key: str = Query("orders", description="示例数据标识: orders / customers")):
    """
    @brief 加载内置示例数据，供新用户快速体验
    @param sample_key 示例数据标识
    @return 与 /api/upload 相同结构的上传结果
    """
    # 查找 sample-data 目录（PyInstaller 打包后位于 _MEIPASS，开发环境回退项目相对路径）
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        sample_dir = os.path.join(sys._MEIPASS, "sample-data")
    else:
        api_dir = os.path.dirname(os.path.abspath(__file__))  # .../backend/app/api
        backend_dir = os.path.dirname(os.path.dirname(api_dir))  # .../backend
        project_dir = os.path.dirname(backend_dir)  # .../ecommerce-data-agent
        sample_dir = os.path.join(project_dir, "sample-data")

    sample_info = next((s for s in _SAMPLE_FILES if s["key"] == sample_key), None)
    if sample_info is None:
        raise HTTPException(status_code=400, detail=f"未知的示例数据: {sample_key}，可用: {[s['key'] for s in _SAMPLE_FILES]}")

    file_path = os.path.join(sample_dir, sample_info["name"])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"示例数据文件不存在: {sample_info['name']}")

    # 读取文件
    with open(file_path, "rb") as f:
        content = f.read()

    file_size_kb = len(content) // 1024
    ext = os.path.splitext(sample_info["name"])[1].lower()
    file_type = ext.lstrip(".")

    # 解析文件
    try:
        df, columns_info = parse_file(content, sample_info["name"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"示例数据解析失败: {str(e)}")

    if df.empty:
        raise HTTPException(status_code=500, detail="示例数据内容为空")

    # 平台模板匹配
    platform_result = match_platform(df)

    # 名称带「示例」前缀
    base_name = f"示例{sample_info['description']}"

    # 检查是否已存在同名数据源，若存在则替换
    db = SessionLocal()
    try:
        existing = db.query(DataSource).filter(DataSource.name == base_name).first()
    finally:
        db.close()

    if existing:
        from app.services.data_ingestion import delete_datasource
        delete_datasource(existing.id)

    # 数据校验
    try:
        validation_report = validate_data(df)
    except Exception as e:
        validation_report = {"error": str(e), "overall_score": 0}

    # 入库
    try:
        result = ingest_dataframe(
            df=df,
            name=base_name,
            file_path=sample_info["name"],
            file_type=file_type,
            file_size_kb=file_size_kb,
            mode="replace",
            columns_meta=columns_info,
            platform=platform_result["platform"],
            column_mapping=platform_result["column_mapping"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"示例数据入库失败: {str(e)}")

    return {
        **result,
        "name": base_name,
        "file_type": file_type,
        "file_size_kb": file_size_kb,
        "validation_report": validation_report,
        "platform": platform_result,
        "description": sample_info["description"],
    }
