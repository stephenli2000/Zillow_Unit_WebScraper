import pandas as pd
import sys
import argparse
import re
import operator

def parse_args():
    parser = argparse.ArgumentParser(description="Filter and summarize Zillow unit listings.")
    parser.add_argument("json_file", help="Input JSON file")
    parser.add_argument("--date", help="Filter by availability date (case-insensitive, e.g. 'now', 'Nov')")
    parser.add_argument("--bed", help="Filter by number of bedrooms, supports >, >=, <, <=, = (e.g. --bed '>=2')")
    parser.add_argument("--bath", help="Filter by number of bathrooms, supports >, >=, <, <=, = (e.g. --bath '<2')")
    return parser.parse_args()


def parse_numeric_filter(expr):
    """Parse numeric filter like '>2', '<=2', '=2'."""
    if not expr:
        return None, None
    match = re.match(r'^\s*(>=|<=|>|<|=)?\s*(\d+(?:\.\d+)?)\s*$', expr)
    if not match:
        return None, None
    op_str, value = match.groups()
    op_str = op_str or '='
    value = float(value)
    ops = {'>': operator.gt, '>=': operator.ge, '<': operator.lt, '<=': operator.le, '=': operator.eq}
    return ops[op_str], value


def clean_numeric(value):
    """Extract numeric part of rent or sqft."""
    if isinstance(value, str):
        m = re.search(r"[\d,]+", value)
        if m:
            return float(m.group(0).replace(",", ""))
    return None


def extract_bed_bath(layout):
    """Extract numeric bed/bath counts from layout string."""
    if not isinstance(layout, str):
        return None, None
    bed_match = re.search(r"(\d+)\s*bd", layout, re.IGNORECASE)
    bath_match = re.search(r"(\d+(?:\.\d+)?)\s*ba", layout, re.IGNORECASE)
    bed = int(bed_match.group(1)) if bed_match else None
    bath = float(bath_match.group(1)) if bath_match else None
    return bed, bath


def apply_filter(df, col, op_func, value):
    """Apply operator-based filter."""
    if op_func and value is not None:
        df = df[df[col].apply(lambda x: op_func(x, value) if pd.notnull(x) else False)]
    return df


def main():
    args = parse_args()

    try:
        df = pd.read_json(args.json_file)
    except Exception as e:
        print(f"Error reading {args.json_file}: {e}")
        sys.exit(1)

    cols = ["property_url", "unit_number", "layout", "sqft", "availability", "rent"]
    df = df[[c for c in cols if c in df.columns]].copy()

    df["rent_value"] = df["rent"].apply(clean_numeric)
    df["sqft_value"] = df["sqft"].apply(clean_numeric)
    df[["bedrooms", "bathrooms"]] = df.apply(
        lambda row: pd.Series(extract_bed_bath(row["layout"])), axis=1
    )

    # Parse numeric filters
    bed_op, bed_val = parse_numeric_filter(args.bed)
    bath_op, bath_val = parse_numeric_filter(args.bath)

    # Apply filters
    df = apply_filter(df, "bedrooms", bed_op, bed_val)
    df = apply_filter(df, "bathrooms", bath_op, bath_val)

    if args.date:
        df = df[df["availability"].astype(str).str.contains(args.date, case=False, na=False)]

    # Display
    pd.set_option("display.max_rows", None)
    pd.set_option("display.width", 200)
    pd.set_option("display.colheader_justify", "center")
    print(df.to_string(index=False))

    # Summary
    if not df.empty and df["rent_value"].notna().any() and df["sqft_value"].notna().any():
        avg_rent = df["rent_value"].mean()
        min_rent = df["rent_value"].min()
        max_rent = df["rent_value"].max()
        avg_sqft = df["sqft_value"].mean()
        avg_rent_per_sqft = avg_rent / avg_sqft if avg_sqft > 0 else None

        print("\n--- Summary ---")
        print(f"Listings matched: {len(df)}")
        print(f"Average Rent: ${avg_rent:,.0f}")
        print(f"Lowest Rent:  ${min_rent:,.0f}")
        print(f"Highest Rent: ${max_rent:,.0f}")
        if avg_rent_per_sqft:
            print(f"Average $/sqft: ${avg_rent_per_sqft:,.2f}")
    else:
        print("\nNo matching listings or missing rent/sqft data for stats.")


if __name__ == "__main__":
    main()

