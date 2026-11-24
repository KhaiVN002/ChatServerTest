"""Build and query the three LANL baseline demonstrations."""

import argparse
import json
import re
import unicodedata
from pathlib import Path
from tempfile import NamedTemporaryFile


BASE = Path(__file__).resolve().parent
DATA = BASE / "data" / "lanl_baseline.json"
RAW = BASE.parent / "logWin" / "extracted"
DAY = 86_400
HALF_WINDOW = 300
REFERENCE_DAYS = 7

CASES = {
    # Fixed demo fixtures selected by inspecting LANL records for visible
    # changes. These centers are sample coordinates, not LANL attack labels.
    # LANL's published documentation does not specify these center choices.
    "auth": ("C706", 1_174_287, "auth.txt", 9, "lần xác thực thất bại", 20),
    "flows": ("C5778", 1_760_026, "flows.txt", 9, "máy đích khác nhau", 10),
    "proc": ("C19938", 1_174_287, "proc.txt", 5, "mã tiến trình khác nhau có sự kiện Start", 10),
}

QUESTIONS = (
    "Máy nào có số lần xác thực thất bại tăng đột biến?",
    "Máy nào kết nối tới nhiều máy đích bất thường?",
    "Máy nào khởi chạy nhiều tiến trình bất thường?",
)


def file_time(raw):
    return int(raw.partition(b",")[0])


def seek_near(file, length, start):
    """LANL text files are ordered by seconds. Land on a complete record before start."""
    low, high = 0, length
    while high - low > 65_536:
        middle = (low + high) // 2
        file.seek(middle)
        file.readline()
        row = file.readline()
        if row and file_time(row) < start:
            low = file.tell()
        else:
            high = middle
    file.seek(low)


def normalize_event(metric, fields, target):
    if metric == "auth" and fields[4] == target:
        return dict(account=fields[1], target_account=fields[2], src=fields[3], dst=fields[4],
                    method=fields[5], logon_type=fields[6], orientation=fields[7], outcome=fields[8])
    if metric == "flows" and fields[2] == target and fields[4] not in (target, "?", ""):
        return dict(src=fields[2], dst=fields[4], source_port=fields[3], port=fields[5],
                    duration=fields[1], protocol=fields[6], packets=fields[7], bytes=fields[8])
    if metric == "proc" and fields[2] == target:
        return dict(account=fields[1], src=fields[2], process=fields[3], outcome=fields[4])
    return None


def metric_key(metric, event):
    if metric == "auth" and event["outcome"] in {"Fail", "Failure"}:
        return event["id"]
    if metric == "flows":
        return event["dst"]
    if metric == "proc" and event["outcome"] == "Start" and event["process"] not in ("?", ""):
        return event["process"]
    return None


def collect_window(file, length, filename, metric, width, host, center, reference):
    start, end = center - HALF_WINDOW, center + HALF_WINDOW
    seek_near(file, length, start)
    offset = file.tell()
    previous = -1
    events, examples, examples_keys, counted = [], [], set(), set()
    for raw in file:
        position, offset = offset, offset + len(raw)
        time = file_time(raw)
        if time < previous:
            raise ValueError(f"Thời gian giảm trong {filename}, byte {position}.")
        previous = time
        if time > end:
            break
        if time < start:
            continue
        line = raw.rstrip(b"\r\n").decode("utf-8")
        fields = line.split(",")
        if len(fields) != width:
            raise ValueError(f"Sai số cột trong {filename}, byte {position}.")
        event = normalize_event(metric, fields, host)
        if event is None:
            continue
        event.update(id=f"lanl:{filename}:{position}", time=time, source=filename,
                     line=line, offset=position, kind=metric)
        events.append(event)
        key = metric_key(metric, event)
        if key is None:
            continue
        counted.add(key)
        distinct = (event.get("src"), event.get("account")) if metric == "auth" else key
        if len(examples) < 4 and distinct not in examples_keys:
            examples.append(event["id"])
            examples_keys.add(distinct)
    return dict(id=f"lanl:{metric}:{host}:{center}", start=start, end=end, center=center,
                reference=reference, value=len(counted), records=len(events),
                examples=examples, events=events)


def build(raw_dir, stage):
    cases = {}
    for metric, (host, center, filename, width, unit, minimum) in CASES.items():
        path = raw_dir / filename
        length = path.stat().st_size
        through = 0 if stage == "replay" else 1
        with path.open("rb") as file:
            windows = [
                collect_window(file, length, filename, metric, width, host, center - days * DAY, days > 0)
                for days in range(REFERENCE_DAYS, through - 1, -1)
            ]
        if len(windows) != REFERENCE_DAYS + (stage == "replay") or any(not window["records"] for window in windows):
            raise ValueError(f"Thiếu log cho một cửa sổ mẫu của {host} trong {filename}.")
        cases[metric] = dict(id=f"lanl:baseline:{metric}", metric=metric, host=host,
                             unit=unit, minimum=minimum, windows=windows)
    return {"stage": stage, "cases": cases}


def write_snapshot(data, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", dir=destination.parent, encoding="utf-8", delete=False) as file:
        temporary = Path(file.name)
        try:
            json.dump(data, file, ensure_ascii=False, separators=(",", ":"))
        except BaseException:
            file.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def read_snapshot(metric, filename=DATA):
    return json.loads(filename.read_text(encoding="utf-8"))["cases"][metric]


def parse_question(message):
    text = unicodedata.normalize("NFD", message.casefold()).replace("đ", "d")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = " ".join(text.split())
    if re.search(r"\b(hom nay|hom qua|bay gio|vua roi|gan day|\d+\s*(gio|phut|ngay)\s*(qua|truoc))\b", text):
        return None, None
    if re.search(r"\b\d{5,}\b", text):
        return None, None
    patterns = {
        "auth": r"\b(xac thuc|dang nhap)\b.{0,50}\b(that bai|loi)\b",
        "flows": r"\b(ket noi|luong mang)\b.{0,55}\b(nhieu may|may dich|bat thuong|dot bien)\b",
        "proc": r"\b(khoi chay|chay nhieu|tien trinh)\b.{0,55}\b(tien trinh|bat thuong|dot bien|tang)\b",
    }
    matches = [metric for metric, pattern in patterns.items() if re.search(pattern, text)]
    hosts = set(re.findall(r"\bc\d+\b", text))
    if len(matches) != 1 or len(hosts) > 1:
        return None, None
    return matches[0], next(iter(hosts)).upper() if hosts else None


def empty(reply):
    return dict(reply=reply, entities=[], evidence=[], graph=[])


def evidence_path(event):
    origin = event.get("src") or event.get("account")
    target = event.get("dst") or event.get("process")
    label = {"auth": "Xác thực thất bại", "flows": "Luồng mạng", "proc": "Khởi chạy"}[event["kind"]]
    detail = event.get("account") or (f"Cổng đích {event['port']}" if event.get("port") else "")
    return dict(id=event["id"], origin=origin, target=target, label=label,
                detail=detail, time=event["time"])


def answer(case, host):
    if host and host != case["host"]:
        return empty(f"Mẫu này theo dõi `{case['host']}`. Chưa có dữ liệu mẫu tương ứng cho `{host}`.")
    windows = case["windows"]
    baseline = [window["value"] for window in windows if window["reference"]]
    maximum = max(baseline)
    threshold = max(case["minimum"], 2 * maximum)
    baseline_summary = f"7 cửa sổ tham chiếu cùng khung giờ (xấp xỉ 10 phút), từ cũ đến mới: {', '.join(map(str, baseline))}."
    current = next((window for window in windows if not window["reference"]), None)
    if current is None:
        return empty(f"Máy `{case['host']}` đã có baseline. {baseline_summary} Chạy bước replay để nạp cửa sổ kiểm thử.")
    measured = current["value"]
    flagged = measured >= threshold
    events = {event["id"]: event for event in current["events"]}
    examples = [events[event_id] for event_id in current["examples"]]
    signal = "Có tín hiệu bất thường." if flagged else "Chưa đạt ngưỡng đánh dấu bất thường."
    reply = (
        f"Máy `{case['host']}` ghi nhận {measured} {case['unit']} "
        f"trong khoảng giây {current['start']}–{current['end']} của mẫu LANL. "
        f"{baseline_summary} Mức cao nhất trước đó là {maximum}. "
        f"Ngưỡng demo là {threshold} (lấy mức lớn hơn giữa {case['minimum']} và 2 lần mức cao nhất). {signal}"
    )
    return {
        "reply": reply,
        "entities": [{"type": "Máy", "value": case["host"]}],
        "evidence": [dict(source=e["source"], time=e["time"], line=e["line"], offset=e["offset"]) for e in examples],
        "graph": [evidence_path(event) for event in examples],
        "baseline": dict(previous=baseline, current=measured, threshold=threshold, flagged=flagged),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("baseline", "replay"), default="replay")
    parser.add_argument("--raw-dir", type=Path, default=RAW)
    parser.add_argument("--output", type=Path, default=DATA)
    parser.add_argument("--neo4j", action="store_true", help="Nạp đồ thị vào Neo4j theo các biến NEO4J_*")
    args = parser.parse_args()
    data = build(args.raw_dir, args.stage)
    if args.neo4j:
        from lanl_neo4j import open_driver, publish

        with open_driver() as driver:
            publish(driver, data)
    write_snapshot(data, args.output)
    for case in data["cases"].values():
        print(f"{case['host']} ({case['metric']}): {[w['value'] for w in case['windows']]}")
    print(args.output)


if __name__ == "__main__":
    main()
