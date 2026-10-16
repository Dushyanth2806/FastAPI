"""Read-only schema check. Prints collection names, counts and field names/types only (no values, so no PII)."""
import config
from db import get_db


def describe(col):
    doc = col.find_one()
    fields = {k: type(v).__name__ for k, v in (doc or {}).items()}
    print(f"  {col.name}: {col.count_documents({})} documents")
    for k, t in fields.items():
        print(f"    {k}: {t}")


def main():
    db = get_db()
    names = sorted(db.list_collection_names())
    print("Collections:", ", ".join(names))
    for name in (config.PRODUCTS_COLLECTION, config.SUPPLIERS_COLLECTION):
        describe(db[name])
    po = [n for n in names if "purchase" in n.lower() or n.lower() in ("po", "pos", "orders")]
    print("Purchase-order candidates:", po or "none found")
    for n in po:
        describe(db[n])


if __name__ == "__main__":
    main()
