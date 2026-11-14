#!/usr/bin/env python3
"""동행복권 내부 JSON을 검증해 공개 데이터로 저장한다. 실패 시 기존 파일 보존."""
from __future__ import annotations
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "latest.json"
KST = ZoneInfo("Asia/Seoul")
FIRST_DRAW = date(2002, 12, 7)
SOURCE_LATEST = "https://www.dhlottery.co.kr/lt645/selectPstLt645Info.do"
SOURCE_AROUND = "https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do"

def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; LottoPublicResultUpdater/1.0)",
        "Accept": "application/json, text/javascript, */*;q=0.5",
        "Referer": "https://www.dhlottery.co.kr/lt645/result",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=18) as response:
        content_type = response.headers.get("Content-Type", "").lower()
        body = response.read(2_000_000)
    if "json" not in content_type and not body.lstrip().startswith(b"{"):
        raise ValueError(f"JSON 응답 아님 (Content-Type: {content_type})")
    doc = json.loads(body.decode("utf-8-sig"))
    if not isinstance(doc, dict):
        raise ValueError("최상위 객체가 JSON object가 아님")
    return doc

def expected_draw_number(today: date) -> int:
    return max(0, 1 + (today - FIRST_DRAW).days // 7)

def integer(row: dict, key: str, *, min_value: int = 0, max_value: int = 10**13) -> int:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{key}: 정수 데이터 없음")
    if isinstance(value, str) and (not value.isascii() or not value.isdigit()):
        raise ValueError(f"{key}: 숫자가 아님")
    result = int(value)
    if result < min_value or result > max_value:
        raise ValueError(f"{key}: 허용 범위 초과")
    return result

def parse_draw(row: dict, today: date, source_url: str) -> dict:
    number = integer(row, "ltEpsd", min_value=1, max_value=100000)
    draw_date = datetime.strptime(str(row.get("ltRflYmd", "")), "%Y%m%d").date()
    if draw_date > today or draw_date.weekday() != 5:
        raise ValueError("미래 날짜 또는 토요일이 아닌 추첨일")
    if draw_date < FIRST_DRAW or (draw_date - FIRST_DRAW).days % 7:
        raise ValueError("추첨일 주차가 실제 달력과 맞지 않음")
    if 1 + (draw_date - FIRST_DRAW).days // 7 != number or number > expected_draw_number(today):
        raise ValueError("회차와 추첨일/현재 날짜가 일치하지 않음")
    nums = [integer(row, f"tm{i}WnNo", min_value=1, max_value=45) for i in range(1, 7)]
    bonus = integer(row, "bnsWnNo", min_value=1, max_value=45)
    if len(set(nums)) != 6 or bonus in nums:
        raise ValueError("당첨번호 중복 또는 보너스 번호 오류")
    ranks = {}
    for rank in (1, 2, 3):
        winners = integer(row, f"rnk{rank}WnNope", max_value=5_000_000)
        prize = integer(row, f"rnk{rank}WnAmt", max_value=10**12)
        if (winners == 0) != (prize == 0):
            raise ValueError(f"{rank}등 게임수/금액의 0 처리 불일치")
        ranks[str(rank)] = {"winners": winners, "prize_per_game": prize}
    return {
        "schema_version": 1, "status": "verified", "draw_no": number,
        "draw_date": draw_date.isoformat(), "numbers": sorted(nums),
        "bonus": bonus, "ranks": ranks,
        "source_url": "https://www.dhlottery.co.kr/lt645/result",
        "source_query": source_url,
        "verified_at_kst": datetime.now(KST).isoformat(timespec="seconds"),
    }

def rows_from_payload(payload: dict) -> list:
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("list"), list):
        raise ValueError("data.list 배열을 찾을 수 없음")
    rows = [x for x in data["list"] if isinstance(x, dict)]
    if not rows:
        raise ValueError("당첨 결과가 비어 있음")
    return rows

def parse_latest(payload: dict, today: date, url: str) -> dict:
    candidates = []
    for row in rows_from_payload(payload):
        try:
            candidates.append(parse_draw(row, today, url))
        except (ValueError, TypeError, OverflowError):
            continue
    if not candidates:
        raise ValueError("날짜·회차·금액 검증에 통과한 추첨 결과 없음")
    return max(candidates, key=lambda r: r["draw_no"])

def read_previous() -> dict | None:
    if not OUTPUT.exists():
        return None
    doc = json.loads(OUTPUT.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("기존 데이터 JSON 객체 오류")
    return doc

def update() -> bool:
    today = datetime.now(KST).date()
    planned = expected_draw_number(today)
    urls = [SOURCE_LATEST, SOURCE_AROUND + "?" + urllib.parse.urlencode({
        "srchDir": "center", "srchLtEpsd": planned,
    })]
    errors = []
    latest = None
    for url in urls:
        try:
            parsed = parse_latest(fetch_json(url), today, url)
            if latest is None or parsed["draw_no"] > latest["draw_no"]:
                latest = parsed
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
    if latest is None:
        raise RuntimeError("동행복권 조회 실패. 기존 데이터를 보존합니다.\n" + "\n".join(errors))
    old = read_previous()
    if old and int(old.get("draw_no", 0)) > latest["draw_no"]:
        raise RuntimeError("더 과거 회차로의 덮어쓰기 방지")
    if old and old.get("status") == "verified" and old.get("draw_no") == latest["draw_no"]:
        for field in ("draw_date", "numbers", "bonus", "ranks"):
            if old.get(field) != latest[field]:
                raise RuntimeError(f"동일 회차 {field} 데이터 변경. 수동 확인 필요")
        print(f"변경 없음: 제{latest['draw_no']}회")
        return False
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"갱신 완료: 제{latest['draw_no']}회, {latest['draw_date']}")
    for err in errors:
        print("보조 경로 경고:", err, file=sys.stderr)
    return True

if __name__ == "__main__":
    try:
        update()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
