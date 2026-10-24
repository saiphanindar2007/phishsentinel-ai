"""
PhishSentinel AI — CSV export helpers
-----------------------------------------
Exported verdicts contain attacker-controlled text (URLs, sender names).
If an analyst opens the CSV in Excel/Sheets, a cell starting with
= + - @ is executed as a formula ("CSV injection"). Neutralise those by
prefixing a single quote, the standard OWASP mitigation.
"""
import csv
import io
from typing import Iterable, List

_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value) -> str:
    s = "" if value is None else str(value)
    return "'" + s if s.startswith(_DANGEROUS) else s


def rows_to_csv(header: List[str], rows: Iterable[Iterable]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in rows:
        writer.writerow([csv_safe(c) for c in row])
    return buf.getvalue()
