"""
test_search.py：搜尋小測驗（階段 4）

讀 eval/search_questions.csv 裡的題目，每題各跑兩次：
  沒加分（只看意思）  vs  有加分（意思＋名字對上加分）
看「正確的段落有沒有排進前 3 名」（Top-3 命中率），結果存到 eval/results/。

目前的題目是用小組原本的 3 幅名畫出的「示範題」；階段 4 會換成你自己出的 10 題。
"""

import csv
import sys
import time

import search

QUESTIONS = search.ROOT / "eval" / "search_questions.csv"
RESULT_DIR = search.ROOT / "eval" / "results"


def rank_of_answer(rows: list[dict], artwork_id: str, topic: str) -> int | None:
    """正確段落排第幾名（只看前 3 名）；不在前 3 名就回傳 None。"""
    for i, r in enumerate(rows[:search.TOP_K], start=1):
        p = r["passage"]
        if p.artwork_id == artwork_id and (not topic or p.topic.startswith(topic)):
            return i
    return None


def main() -> int:
    s = search.Searcher()
    if s.stale:
        print("⚠ 資料改過但索引是舊的，請先雙擊 build_index.bat")
    with QUESTIONS.open(encoding="utf-8-sig") as f:
        questions = list(csv.DictReader(f))
    print(f"模型：{s.meta['model']}　題數：{len(questions)}")
    print()
    print(f"{'題號':<4} {'沒加分':<6} {'有加分':<6} 問題")
    rows_out = []
    hits = {"沒加分": 0, "有加分": 0}
    for q in questions:
        r_plain = rank_of_answer(s.score_all(q["question"], use_bonus=False), q["expected_artwork"], q["expected_topic"])
        r_bonus = rank_of_answer(s.score_all(q["question"], use_bonus=True), q["expected_artwork"], q["expected_topic"])
        hits["沒加分"] += r_plain is not None
        hits["有加分"] += r_bonus is not None
        show = lambda r: f"第{r}名" if r else "沒命中"
        print(f"{q['id']:<5} {show(r_plain):<6} {show(r_bonus):<6} {q['question']}")
        rows_out.append({**q, "rank_without_bonus": r_plain or "", "rank_with_bonus": r_bonus or ""})

    n = len(questions)
    print()
    print(f"Top-3 命中率　沒加分：{hits['沒加分']}/{n}（{hits['沒加分'] / n:.0%}）"
          f"　有加分：{hits['有加分']}/{n}（{hits['有加分'] / n:.0%}）")
    if s.meta["fake"]:
        print("（注意：這是假向量的結果，只能證明程式會跑，不代表真實效果）")

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULT_DIR / f"search_{time.strftime('%m%d_%H%M')}.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(rows_out)
    print(f"結果已存到 {out.relative_to(search.ROOT)}（可以用 Excel 開）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
