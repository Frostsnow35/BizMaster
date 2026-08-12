"""临时调试脚本：查看 format_variants 真实内容"""
import asyncio, sys

from app.core.database import SessionLocal
from app.models.data_source import DataSource
from app.api.chat import _get_data_summary
from app.agent.graph import run_agent
from app.agent.tools.schema import get_all_tools

LOG = "debug_formats_out.txt"


def log(*args):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(" ".join(str(a) for a in args) + "\n")


async def main():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("")
    db = SessionLocal()
    ds = db.query(DataSource).first()
    db.close()
    if not ds:
        log("无数据源")
        return
    summary = _get_data_summary(ds.id)
    tools = get_all_tools()
    async for event in run_agent(
        question="各品类销售额排名",
        data_source_id=ds.id,
        tools=tools,
        data_summary=summary,
        graph=None,
        config=None,
        resume_mode=False,
    ):
        t = event.get("type")
        if t == "done":
            log("=== final_response ===")
            log((event.get("final_response") or "")[:800])
            log("\n=== format_variants ===")
            for k, v in (event.get("format_variants") or {}).items():
                log(f"\n--- {k} ---")
                log((v or "")[:800])
            break
        elif t == "error":
            log("ERROR:", event.get("message"))
            break


asyncio.run(main())

