from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.models.emotion_record import EmotionRecord


def weekly_trends(records: list[EmotionRecord]) -> list[dict[str, float | str]]:
    points: dict[str, list[float]] = defaultdict(list)
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=7)
    for record in records:
        if record.created_at < start:
            continue
        key = record.created_at.strftime("%Y-%m-%d")
        points[key].append(record.confidence)

    output = []
    for day in range(7):
        cur = (start + timedelta(days=day + 1)).strftime("%Y-%m-%d")
        avg = sum(points[cur]) / len(points[cur]) if points[cur] else 0.0
        output.append({"date": cur, "avg_confidence": round(avg, 4)})
    return output