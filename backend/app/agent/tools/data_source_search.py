"""
@brief 数据源搜索工具

按关键词搜索资源库中的数据源，供 Agent 在单表无法满足需求时查找其他可用表。
"""
from typing import Dict, Any, List
from app.core.database import SessionLocal
from app.models.data_source import DataSource


def search_data_sources(keywords: str) -> Dict[str, Any]:
    """
    @brief 按关键词搜索数据源
    @param keywords 搜索关键词（空格或逗号分隔）
    @return {"matches": [{"id", "name", "purpose", "row_count", "columns": [...]}], "total": int}
    """
    db = SessionLocal()
    try:
        sources = db.query(DataSource).order_by(DataSource.created_at.desc()).all()
        kw_list = [k.strip().lower() for k in keywords.replace(",", " ").split() if k.strip()]
        matches: List[dict] = []

        for s in sources:
            all_text = f"{s.name} {s.purpose or ''} ".lower()
            col_names = " ".join(
                str(c.get("name", "")) for c in (s.columns_meta or [])
            ).lower()
            all_text += col_names

            score = sum(1 for k in kw_list if k in all_text)
            if score > 0:
                matches.append({
                    "id": s.id,
                    "name": s.name,
                    "purpose": s.purpose or "通用数据",
                    "row_count": s.row_count,
                    "columns": [
                        {"name": c.get("name", ""), "dtype": c.get("dtype", "")}
                        for c in (s.columns_meta or [])
                    ],
                    "score": score,
                })

        matches.sort(key=lambda m: m["score"], reverse=True)
        return {"matches": matches, "total": len(matches)}
    finally:
        db.close()
