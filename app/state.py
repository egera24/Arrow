import csv
import io
from datetime import datetime

from app.models import BatchAnalyzeResponse, TicketInput


_last_batch_result: BatchAnalyzeResponse | None = None


def set_last_batch_result(result: BatchAnalyzeResponse) -> None:
    global _last_batch_result
    _last_batch_result = result


def get_last_batch_result() -> BatchAnalyzeResponse | None:
    return _last_batch_result


def parse_tickets_csv(content: bytes) -> list[TicketInput]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    tickets: list[TicketInput] = []
    for row in reader:
        created_at = None
        if row.get("created_at"):
            created_at = datetime.fromisoformat(row["created_at"])
        tickets.append(
            TicketInput(
                ticket_id=row["ticket_id"],
                subject=row["subject"],
                description=row["description"],
                created_at=created_at,
            )
        )
    return tickets


def batch_result_to_csv(result: BatchAnalyzeResponse) -> str:
    output = io.StringIO()
    fieldnames = [
        "ticket_id",
        "category",
        "priority",
        "sentiment",
        "summary",
        "suggested_tags",
        "rationale",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for item in result.classifications:
        writer.writerow(
            {
                "ticket_id": item.ticket_id,
                "category": item.category,
                "priority": item.priority,
                "sentiment": item.sentiment,
                "summary": item.summary,
                "suggested_tags": "|".join(item.suggested_tags),
                "rationale": item.rationale,
            }
        )
    return output.getvalue()
