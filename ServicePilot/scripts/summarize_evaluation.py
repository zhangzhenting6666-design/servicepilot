"""Rebuild the dated evaluation index from preserved real records; no model calls."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

PRODUCT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PRODUCT), str(PRODUCT / "scripts")]
from run_evaluation import assert_unchanged, metrics
from servicepilot.session import now

ROOT = PRODUCT / "artifacts/evaluation"
FINAL = ROOT / "eval-run-2026-10-14T143743_0800-858a4efe.json"


def timing(cases):
    seconds = [t["elapsed_seconds"] for c in cases for t in c["turns"] if "elapsed_seconds" in t]
    ordered = sorted(seconds)
    return {"measured_turns": len(seconds), "sum_seconds": round(sum(seconds), 3),
            "mean_seconds": round(statistics.mean(seconds), 3) if seconds else None,
            "median_seconds": round(statistics.median(seconds), 3) if seconds else None,
            "p95_seconds_nearest_rank": ordered[math.ceil(len(ordered) * 0.95) - 1] if ordered else None,
            "scope": "OrderSession.ask wall time; excludes human review/key/freeze waits, not a speed guarantee"}


def evidence_ref(path):
    payload = path.read_bytes()
    return {"path": str(path.relative_to(PRODUCT)).replace("\\", "/"),
            "byte_sha256": hashlib.sha256(payload).hexdigest(),
            "canonical_lf_sha256": hashlib.sha256(payload.replace(b"\r\n", b"\n")).hexdigest()}


def main():
    final = json.loads(FINAL.read_text(encoding="utf-8"))
    assert_unchanged(final["frozen_version"])
    assert final["status"] == "reviewed_passed" and final["development_round"] == 4 and final["holdout_round"] == 2
    assert final["normal_data_unchanged"]
    assert len(final["cases"]) == 25 and all(c["verdict"] == "passed" and all(c["checks"].values()) for c in final["cases"])
    assert all(c["version"]["source_hashes"] == final["frozen_version"]["source_hashes"] for c in final["cases"])
    rounds = []
    for path in sorted(ROOT.glob("eval-run-*.json")):
        if path.name.endswith(".review-control.json"):
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        assert record["manifest_sha256"] == final["manifest_sha256"]
        splits = {}
        for split, denominator in (("development", 15), ("holdout", 10)):
            cases = [c for c in record["cases"] if c["split"] == split]
            if cases:
                splits[split] = {"denominator": denominator, **metrics(cases), "timing": timing(cases),
                                 "incomplete_cases": [c["case_id"] for c in cases if c["verdict"] == "running"],
                                 "not_run": [c["id"] for c in record["manifest"]["cases"]
                                     if c["split"] == split and c["id"] not in {item["case_id"] for item in cases}]}
        rounds.append({"evidence": evidence_ref(path), "raw_status": record["status"],
                       "development_round": record.get("development_round"), "holdout_round": record.get("holdout_round"),
                       "version": record["version"], "error_type": record.get("error_type"), "splits": splits,
                       "observed_metrics": metrics(record["cases"]),
                       "interpretation": "Early development round 2 was stopped after DEV01 while aligning the committed startup baseline; raw pending state retained" if record.get("development_round") == 2 else None})
    totals = {key: sum(r["observed_metrics"]["usage"][key] for r in rounds)
              for key in ("requests", "input_tokens", "output_tokens", "total_tokens")}
    cases = [{"case_id": c["case_id"], "split": c["split"], "verdict": c["verdict"],
              "definition": c["definition"], "checks": c["checks"], "reply_review": c["reply_review"],
              "version_commit": c["version"]["commit"], "elapsed_seconds": c["elapsed_seconds"],
              "usage": metrics([c])["usage"],
              "steps": [{"input": t["input"], "session_id": t["session_id"], "session_name": t["session_name"],
                         "starting_agent": t["starting_agent"], "final_agent": t["final_agent"],
                         "actual_final_answer": t["final_answer"], "elapsed_seconds": t["elapsed_seconds"], "usage": t["usage"],
                         "fault_state_before": t["fault_state_before"], "source_accesses": t["source_accesses"],
                         "public_execution_events": [e for e in t["events"] if e["type"] != "model_request"]} for t in c["turns"]]}
             for c in final["cases"]]
    summary = {"reviewed_at": now(), "evidence_kind": "real_backend_evaluation_review",
               "final_raw_record": evidence_ref(FINAL), "tested_frozen_version": final["frozen_version"],
               "manifest_sha256": final["manifest_sha256"], "manifest": "evaluations/cases-v1.json",
               "development": {"round": 4, "passed": 15, "total": 15, "metrics": final["development_metrics"],
                               "timing": timing([c for c in final["cases"] if c["split"] == "development"])},
               "holdout_first_round": {"round": 1, "passed": 4, "total": 10, "incomplete": ["HOLD05"],
                                       "not_run": ["HOLD06", "HOLD07", "HOLD08", "HOLD09", "HOLD10"], "runtime_error": "PermissionError"},
               "holdout_retest": {"round": 2, "passed": 10, "total": 10, "metrics": final["holdout_metrics"],
                                  "timing": timing([c for c in final["cases"] if c["split"] == "holdout"])},
               "history": rounds, "all_runs_observed_usage": totals, "cases": cases,
               "quality_fix": {"initial_observation": "development-round1-quality-review.json",
                               "fixed_by_commit": "7bf1208", "regression_case_ids": ["DEV01", "DEV06", "DEV10", "DEV14"],
                               "verdict": "These actual replies were reviewed again in final development round 4; unsupported offers absent in these observations"},
               "persistence_repair": {"initial_interruption": "holdout-round1-interruption-review.json", "fixed_by_commit": "4f49d09",
                                      "http_retries_remain_zero": True, "disk_retries_only": True},
               "normal_data_unchanged": True, "current_frozen_source_hashes_match": True,
               "limitations": ["公开预先划分，不是外部独立盲评；留出第2轮是重测，不代替首轮",
                   "固定小样本与每题单次结果，不代表任意表达、长会话或总体成功率",
                   "开发首轮15/15仍有额外文案质量风险，已经保留并在留出前处理；没有事后改固定判据",
                   "Windows输入法候选字组合态Enter待确认，不计通过或失败",
                   "运行中的E01旧页面服务需重启才能加载新代码，本轮后台评测不是新版UI真实验收",
                   "README、演示和个人贡献材料留到评测结果交接后；无真实退款、工单、接口、登录或部署"],
               "offline_checks": "artifacts/orders/local-check-2026-10-14T143650_0800-cf086aa7.json"}
    out = ROOT / "evaluation-review-2026-10-14.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    doc = ["# ServicePilot 25条评测报告", "", "2026-10-14。真实后台评测，非页面预设输出；当前冻结代码4f49d09，分支feature/order-query。", "",
           "参数化清单：[cases-v1.json](../evaluations/cases-v1.json)。完整结果/原始证据索引：[正式复核](../artifacts/evaluation/evaluation-review-2026-10-14.json)。", "",
           "## 结果", "", "| 阶段 | 结果 | 版本与说明 |", "| --- | --- | --- |",
           "| 开发第1轮 | 15/15 | 8babaa7，固定判据通过；另有4条答复的能力文案观察，未进入留出 |",
           "| 开发第2轮 | 未完成 | 一次早停启动只跑DEV01，原记录待复核；不能计整批通过，用量保留 |",
           "| 开发第3轮 | 15/15 | 7bf1208，文案修订后完整回归，再冻结 |",
           "| 留出第1轮 | 4/10 | 7bf1208，第5条第一步后PermissionError中断；HOLD05未完成，HOLD06–10未运行 |",
           "| 开发第4轮 | 15/15 | 4f49d09，磁盘保存修复后再次完整回归 |",
           "| 留出第2轮 | 10/10 | 同一4f49d09冻结版本，全部重测；不是首次未使用留出结果 |", "",
           "本清单对参与者可见，是公开的预先划分，不宣称外部盲评。每个案例之间全新会话；多轮共用同一会话，DEV11的A/B独立。运行期间未修改冻结代码或清单，故障只改变测试源状态，正常数据前后哈希一致。", "",
           "## 最终同版本的实际用量与耗时", "",
           "| 集合 | 案例/用户轮 | 模型请求 | total tokens | 单轮均值秒 | 单轮p95秒 |", "| --- | --- | --- | --- | --- | --- |"]
    for split in ("development", "holdout_retest"):
        item = summary[split]
        m, t = item["metrics"], item["timing"]
        doc.append(f"| {split} | {m['cases_executed']}/{m['turns']} | {m['usage']['requests']} | {m['usage']['total_tokens']} | {t['mean_seconds']} | {t['p95_seconds_nearest_rank']} |")
    doc += ["", f"最终25条共34轮用户输入、93次模型请求、98400 total tokens。所有保留运行（含重复开发、部分留出与早停）共{totals['requests']}次实际模型请求、{totals['total_tokens']} total tokens，不把重复运行当成更多独立案例，不估算费用。",
            "耗时取实际OrderSession.ask墙钟时间，排除密钥输入、开发复核和冻结等待；p95用nearest-rank，样本较少，不作为速度保证。请求失败时无usage的情况会明确标不完整，本轮已保存的用户轮均有实际usage。", "",
            "## 失败、质量观察与修复", "",
            "首轮开发的固定业务判据没有失败，但FAQ主动建议查签收相关信息、Order提出人工/FAQ真实渠道和配送时效转交超出能力文案边界。原始答复保留，另记[质量观察](../artifacts/evaluation/development-round1-quality-review.json)，没有看完结果后改清单或判据。只调整查询后结尾：解释结果和必要边界，不主动扩大服务；保留用户下一轮实际Agent交接。后续完整开发回归及4条专项观察通过。", "",
            "留出首轮实际运行在HOLD05两轮之间保存记录时PermissionError中断，不是已经完成的模型业务回答失败。独立临时文件复现读者打开目标文件时replace失败、关闭后成功，与读写共享竞争一致；原记录无完整堆栈，不声称唯一来源。[中断复核](../artifacts/evaluation/holdout-round1-interruption-review.json)和[离线复现](../artifacts/evaluation/evidence-lock-reproduction.json)保留。证据写入增加最多约1秒的8次磁盘替换重试；模型HTTP重试仍0。34项离线检查包括实际Windows文件锁和持续失败有界退出。保存原失败记录后，新版本开发回归再冻结重测，不覆盖首轮。", "",
            "一次提交文件名模式未匹配，启动早于有效提交；为对齐可审阅版本停止该启动。它实际完成了DEV01而非零调用，原待复核状态与2798tokens保留，后续从新提交完整运行。", "",
            "## 最终逐条复核索引", "", "原始逐轮输入、session_id、实际路由、工具参数与结果、完整答复、模型参数、source访问、usage、耗时和被测哈希见正式JSON；以下为已人工读过答复的结论。", "",
            "| 编号 | 模型请求 | tokens | 实际复核结论 |", "| --- | --- | --- | --- |"]
    for c in cases:
        reason = c["reply_review"]["reason"].replace("|", "/")
        doc.append(f"| {c['case_id']} | {c['usage']['requests']} | {c['usage']['total_tokens']} | {reason} |")
    doc += ["", "## 复现入口", "", "双击启动评测.cmd，或工作区根目录：", "", "```powershell",
            "& '.\\openai-agents-python-main\\.venv\\Scripts\\python.exe' -X utf8 '.\\ServicePilot\\scripts\\run_evaluation.py' --split both --review-gate", "```", "",
            "仅在本机终端DeepSeek API key:后隐藏输入密钥，不发到聊天或文件。每个案例暂停等待开发助手复核，FREEZE检查点要求开发15条全部通过及明确冻结提交。没有review-gate的单集合运行仍需人工答复复核，不自动视为通过。每次生成新文件与自动递增轮次，旧记录保留。若再次运行，是新轮次而非覆盖本次。", "",
            "## 未完成与下一步", "", "中文正常发送已有用户截图；输入法选字期间Enter仍待人工确认，不标通过/失败。25条小样本不能证明任意问法或长会话，亦不是多Agent优于单Agent的对比。未实现真实退款、工单、登录、业务接口或部署。", "",
            "本轮先交接评测结果、失败原因与未完成项，再根据这些结果完善README、启动说明、三分钟演示和个人贡献。旧E01页面服务需重启才加载新代码，本次后台评测不自动升级为新版本UI实测8/8；后续演示前应复查页面。"]
    (PRODUCT / "docs/2026-10-14-25条评测报告.md").write_text("\n".join(doc) + "\n", encoding="utf-8")
    print(json.dumps({"development": "15/15 round4", "holdout_first": "4/10 interrupted round1",
                      "holdout_retest": "10/10 round2", "all_runs_usage": totals,
                      "development_timing": summary["development"]["timing"], "holdout_timing": summary["holdout_retest"]["timing"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
