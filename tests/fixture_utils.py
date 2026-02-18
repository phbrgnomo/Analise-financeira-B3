import csv
import os


def parse_fixture_csv(filename: str):
    """Parse a fixture CSV into a list of tuples ready for DB insert.

    Returns tuples in the same order used by the `prices` table.
    """
    csv_path = os.path.join(os.path.dirname(__file__), "fixtures", filename)
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                (
                    r.get("ticker"),
                    r.get("date"),
                    float(r.get("open") or 0),
                    float(r.get("high") or 0),
                    float(r.get("low") or 0),
                    float(r.get("close") or 0),
                    float(r.get("adj_close") or 0),
                    int(r.get("volume") or 0),
                    r.get("source"),
                )
            )
    return rows
