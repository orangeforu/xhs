"""工作流实测脚本（上架前质检，README 要求的"逐条实测"自动化部分）。

对 kit-cn 的 10 条工作流逐条做真实 API 实测：
- 从 kit-cn md 中按顺序提取 10 个提示词代码块
- 每条配一个带"埋雷"的真实场景输入（编因果诱饵 / 编共识诱饵 / 藏截止日 / 无数据看它编不编）
- 01/02 额外跑一次"裸模型"对照组，提供待人工判断的对照证据
- 输出独占保存到 CASE/products/ai-office-workflows/qa/<run_id>/，不覆盖历史实测
- API 调用完成不代表质检通过，所有工作流均待人工判定

用法：python ventures/ai_workflow_kit/tools/test_workflows.py（显式运行才读取凭证并调用 API）
"""
import hashlib
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import requests

CASE = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[3]
KIT = CASE / "products" / "ai-office-workflows" / "kit-cn-打工人AI提效工作流包.md"
QA_DIR = KIT.parent / "qa"
MAX_ATTEMPTS = 3  # 包含首次请求，所有失败类型共用此预算
TOKEN_HARD_LIMIT = 32000
DEFAULT_MODEL = "deepseek-v4-flash"


# ---------- 仅运行入口读取 .env，导入不访问凭证 ----------
def load_env():
    env = {}
    env_path = REPO / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def utc_now():
    return datetime.now(UTC).isoformat()


def sha256(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def call_llm(messages, max_tokens=8000, *, env):
    """有限总尝试数 + 单请求 token 硬上限；返回调用证据，不做质量判定。

    只有非空正文且 finish_reason=stop 才算调用完成。截断正文仍保留在
    attempts 中作为失败证据，reasoning_content 永不作为答案或回退输出。
    """
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
        raise ValueError("max_tokens must be a positive integer")
    tokens = min(max_tokens, TOKEN_HARD_LIMIT)
    attempts = []
    for attempt in range(MAX_ATTEMPTS):
        record = {"attempt": attempt + 1, "started_at_utc": utc_now(), "max_tokens": tokens,
                  "output": None, "finish_reason": None}
        retry = True
        try:
            response = requests.post(
                f"{env.get('LLM_BASE_URL', 'https://api.deepseek.com/v1').rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {env['LLM_API_KEY']}"},
                json={"model": env.get("LLM_MODEL", DEFAULT_MODEL), "messages": messages,
                      "temperature": 0.3, "max_tokens": tokens},
                timeout=180,
            )
            record["http_status"] = response.status_code
            if not 200 <= response.status_code < 300:
                record["error"] = f"http_{response.status_code}"
                retry = response.status_code in (429, 500, 502, 503, 504)
            else:
                data = response.json()
                if data.get("error") is not None:
                    record["error"] = "api_error"
                else:
                    choice = data["choices"][0]
                    content = choice["message"].get("content")
                    finish = choice.get("finish_reason")
                    record["output"] = content if isinstance(content, str) else None
                    record["finish_reason"] = finish
                    if finish == "length":
                        record["error"] = "length_limit"
                        tokens = min(tokens * 2, TOKEN_HARD_LIMIT)
                    elif not isinstance(content, str) or not content.strip():
                        record["error"] = "empty_content"
                    elif finish != "stop":
                        record["error"] = "incomplete_response"
                        retry = False
                    elif content.lstrip().startswith("[API ERROR]"):
                        record["error"] = "api_error_content"
                        retry = False
                    else:
                        record["completed_at_utc"] = utc_now()
                        attempts.append(record)
                        return {"status": "completed", "output": content, "error": None, "attempts": attempts}
        except requests.RequestException as exc:
            # 不存异常原文/响应头，避免其中携带凭证；保留安全错误类别。
            record["error"] = type(exc).__name__
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            record["error"] = "invalid_response"
        record["completed_at_utc"] = utc_now()
        attempts.append(record)
        if not retry:
            break
        if attempt + 1 < MAX_ATTEMPTS:
            time.sleep(5 * (attempt + 1))
    return {"status": "failed", "output": None, "error": attempts[-1]["error"], "attempts": attempts}


# ---------- 提取 kit-cn 的 10 个提示词块 ----------
def extract_prompts(text=None):
    if text is None:
        text = KIT.read_text(encoding="utf-8")
    blocks = re.findall(r"```\n(.*?)```", text, re.S)
    if len(blocks) != 10:
        raise ValueError(f"expected 10 prompt blocks, got {len(blocks)}")
    return blocks


# ---------- 场景（每条埋了针对性陷阱）----------
SCENARIOS = {
    1: {
        "name": "周报",
        "input": """以下是我这周的原始碎片，帮我整理：
- 周二 客户A说banner配色不行，要求返工改一版
- 周三 把3月投放数据表更新完了，发给组长了
- 周四 跟市场部对齐了下季度排期的事
- 周五 项目B排期顺延了一周（供应商那边新版本发版晚了）
- 帮李姐改了两页PPT
- 好像还更新了wiki上的流程文档？（记不清是这周还是上周了）""",
        "followup": None,
        "checks": [
            "是否出现『客户A返工 → 项目B延期』编造因果（两件事无关，B延期原因是供应商发版）",
            "『跟市场部对齐』这类无结果项是否被删除",
            "『wiki文档』不确定项是否标注 [待确认] 而非直接写成已完成",
        ],
    },
    2: {
        "name": "会议纪要",
        "input": """以下是今天周会的录音转写片段，帮我出纪要：
……
张经理：这个入库权限的事，我觉得下季度可以再看看。
（几个人附和"可以"）
刘总：行，那先这样。
小王：发票的事我来跟吧。
张经理：好，小王负责发票。
刘总：对了，活动物料记得提前订，别又像上次一样临时抱佛脚。
（没人接话，话题转走了）
陈姐：争取下周把客户名单整理出来吧。
……""",
        "followup": None,
        "checks": [
            "『入库权限』只是『再看看』的讨论，是否被写成『已决定』（编共识陷阱）",
            "『活动物料提前订』没人认领——是否进了『无人认领』而非被安给某人",
            "『争取下周』是模糊日期——截止时间是否如实处理（未定/引用原话）而非擅自写成具体日期",
        ],
    },
    3: {
        "name": "进度同步",
        "input": """帮我把这周进展写成给领导的进度同步。这周做的事：
- 新人培训手册写完了初稿，20页
- 处理了14条客户咨询
- 报销单交了
感觉整体还挺顺的，没什么大事。下周打算把手册剩下的部分弄完。""",
        "followup": None,
        "checks": [
            "我没给任何风险——是否按规定写固定句而非编一条风险",
            "『感觉挺顺』是感受不是事实——输出里是否出现无数字的安慰词",
            "动词是否与材料一致（初稿≠完成）",
        ],
    },
    4: {
        "name": "长文档摘要",
        "input": """我是运营负责人，需要知道这份供应商合同让我们承担了什么义务。

【第1页】合作协议（甲方：我司；乙方：云达科技）。乙方向甲方提供云桌面服务，服务期24个月，自2026年10月1日起算。
【第2页】费用：按席位计费，每席每月120元，合计每月不超过5万元。付款方式为季付。
【第3页】服务水平：可用性承诺99.5%，每低0.1%扣减当季费用1%。
【第4页】任何一方提前终止需提前90天书面通知。
【第5页】（附则）本协议期满前30日内如双方均未书面提出异议，自动续期12个月，续期期内费率上调不超过8%。甲方逾期付款的，按日万分之五支付违约金。本条不受第4条终止通知条款影响的情况：欠费期间乙方有权暂停服务且不视为违约。""",
        "followup": None,
        "checks": [
            "是否挖到第5页附则的三个坑：自动续期+费率上调、日万分之五违约金、欠费暂停服务不算乙方违约",
            "页码引用是否与埋雷位置一致（都在第5页）",
            "是否至少有一条让人意外的坑（而非只复述正文费用条款）",
        ],
    },
    5: {
        "name": "脏表格",
        "input": """帮我看看这个导出数据：
客户名称,签约月份,合同额(万元),回款额(万元)
华兴科技,2026-03,12,12
华兴科技,2026/03,12,12
蓝湾物流,2026-04,8,
蓝湾物流,2026-05,9,9
康明医药,2026-04,15,10
,2026-05,6,6
合计,,,,""",
        "followup": "确认。两行华兴科技是同一客户同月，但一行是我手工补录的，先别去重，按原样处理。",
        "checks": [
            "第一轮是否只复述理解并停下（而非直接出结果）",
            "蓝湾物流4月回款为空——是否列入缺口清单而非填0或沿用9",
            "算术是否正确且展示算式（如合同额合计 12+8+9+15+6=50）",
            "是否遵守『不去重』指令",
        ],
    },
    6: {
        "name": "催办",
        "input": """帮我写催办。事项：设计部的首页改版终稿，我9月15日就发需求了，说好9月22日给，现在拖到28号了还没动静，我们10月初就要上线，真的挺无语的，拖了快两周了，火大。再拖整个项目都要被他们拖黄了。收件人是设计部的周工（平级），如果他还不回可能要抄送他的领导。""",
        "followup": None,
        "checks": [
            "输入里全是情绪（火大/无语/拖黄）——三个版本是否都零情绪",
            "『轻提』版是否真的轻（假设对方只是忘了）而非带刺",
            "是否给三档而非只有一档",
        ],
    },
    7: {
        "name": "PPT大纲",
        "input": "主题：向管理层汇报『客服外包降本方案』。听众：CFO和运营VP，他们最在乎成本节约的真实性和服务质量风险。页数：8页。注意：我手上还没有具体的成本数据。",
        "followup": None,
        "checks": [
            "是否先只给『脊柱』（每页一句takeaway）然后停下等确认，而非直接输出整套大纲",
            "我明说没有数据——是否出现编造的百分比/金额，还是用 [缺数据] 占位",
        ],
    },
    8: {
        "name": "简历改写",
        "input": """帮我把这几条简历条目改强一点：
- 负责公司微信公众号的日常运营
- 参与了双11大促活动的筹备工作
- 协助行政部门做月度费用报表""",
        "followup": None,
        "checks": [
            "我没给任何数字——是否发明『阅读量提升X%』『节省X小时』这类编造指标",
            "是否用 [数字?] 向我追问而非自行补全",
            "『负责/参与/协助』是否被替换",
        ],
    },
    9: {
        "name": "预判领导追问",
        "input": """我下周要向大领导做季度汇报，准备讲这些：
- 上季度我们小程序的转化率是2.1%，环比下降了12%
- 我们上线了新的会员积分体系，用户反馈很好
- 客服响应速度有提升
- 下季度计划做一轮私域促活活动""",
        "followup": None,
        "checks": [
            "问题是否针对我的具体内容（如『降12%的基线是多少』『积分体系好在哪、数据呢』）而非模板题",
            "『用户反馈很好』『响应速度有提升』这类无量化表述是否被点名",
            "给的回答是否只用我给的事实而非编新事实",
        ],
    },
    10: {
        "name": "消息分诊",
        "input": """帮我把今天收到的客户消息分诊：
1. 客户甲：你们系统晚上维护大概几点结束？我明早要用。
2. 客户乙：说实话我对你们这次的服务挺失望的，问题反馈了三次都没解决，我需要你们给个说法。
3. 客户丙：如果方便的话，月底前把明年的报价单发我一下呗，不急。
4. 客户丁：收到，谢谢！
5. 客户戊：我们领导问能不能给个95折，量大可以考虑续约两年。""",
        "followup": None,
        "checks": [
            "客户乙是投诉——必须上报而非替我起草安抚回复",
            "客户丙『月底前』是客气话藏截止日——不得归入缓一缓",
            "客户戊涉及价格与承诺——上报或草稿中只能有 [待我拍板] 而非给出折扣承诺",
            "客户丁无需处理——应归缓一缓或不占动作",
        ],
    },
}

BASELINE = {
    1: "以下是我这周的原始碎片，帮我整理成周报：\n{input}",
    2: "以下是会议转写，帮我整理成会议纪要：\n{input}",
}


def write_evidence(path, data):
    """独占创建：即使 run_id 碰撞或误复用路径，也不得覆盖历史证据。"""
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)


def recorded_call(messages, env):
    return {
        "messages": messages,
        "messages_sha256": sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True)),
        "result": call_llm(messages, env=env),
    }


def run(*, env=None):
    if env is None:
        env = load_env()
    if not env.get("LLM_API_KEY"):
        raise ValueError("LLM_API_KEY is required for an explicit live run")
    # 一次读取源文件，提示词与 hash 必须来自同一份字节快照。
    kit_bytes = KIT.read_bytes()
    prompts = extract_prompts(kit_bytes.decode("utf-8").replace("\r\n", "\n"))
    runner = Path(__file__).resolve()
    started = utc_now()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex
    run_dir = QA_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    metadata = {
        "run_id": run_id, "started_at_utc": started, "model": env.get("LLM_MODEL", DEFAULT_MODEL),
        "source_files": {
            "kit": {"path": str(KIT), "sha256": sha256(kit_bytes)},
            "runner": {"path": str(runner), "sha256": sha256(runner.read_bytes())},
        },
        "limits": {"max_attempts_per_call": MAX_ATTEMPTS, "token_hard_limit": TOKEN_HARD_LIMIT},
        "temperature": 0.3,
        "manual_review_status": "pending",
    }
    write_evidence(run_dir / "manifest.json", metadata)
    entries = []
    failures = 0
    for idx in sorted(SCENARIOS):
        sc = SCENARIOS[idx]
        prompt = prompts[idx - 1]
        print(f"[{idx:02d}] {sc['name']} ...", flush=True)
        entry = {
            "run_id": run_id, "model": metadata["model"], "started_at_utc": utc_now(),
            "workflow": idx, "name": sc["name"], "prompt": prompt, "input": sc["input"],
            "prompt_sha256": sha256(prompt), "input_sha256": sha256(sc["input"]),
            "followup": sc["followup"],
            "followup_sha256": sha256(sc["followup"]) if sc["followup"] else None,
            "manual_checks": sc["checks"], "manual_review_status": "pending",
        }
        messages = [{"role": "user", "content": f"{prompt}\n\n---\n\n{sc['input']}"}]
        first = recorded_call(messages, env)
        entry["rounds"] = [first]
        final = first["result"]
        if sc["followup"] and final["status"] == "completed":
            followup = messages + [
                {"role": "assistant", "content": final["output"]},
                {"role": "user", "content": sc["followup"]},
            ]
            second = recorded_call(followup, env)
            entry["rounds"].append(second)
            final = second["result"]
        entry["execution_status"] = final["status"]
        entry["final_output"] = final["output"]
        calls = list(entry["rounds"])
        if idx in BASELINE:
            entry["baseline"] = recorded_call(
                [{"role": "user", "content": BASELINE[idx].format(input=sc["input"])}], env
            )
            calls.append(entry["baseline"])
        failures += sum(call["result"]["status"] == "failed" for call in calls)
        entry["completed_at_utc"] = utc_now()
        filename = f"run-{idx:02d}.json"
        write_evidence(run_dir / filename, entry)
        entries.append({"workflow": idx, "evidence_file": filename, "execution_status": final["status"],
                        "manual_review_status": "pending"})

    write_evidence(run_dir / "summary.json", {
        **metadata, "completed_at_utc": utc_now(), "entries": entries, "failed_calls": failures,
        "note": "API 调用完成不代表质检通过；所有工作流均待人工判定。",
    })
    print("输出已保存，待人工判定 ->", run_dir)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
