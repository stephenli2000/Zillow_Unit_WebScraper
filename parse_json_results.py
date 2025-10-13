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
    return pd.NA


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
        if col in df.columns:
            valid_mask = pd.notna(df[col])
            # Apply the filter only to the valid rows
            df = df[valid_mask & df.loc[valid_mask, col].apply(lambda x: op_func(x, value))]
    return df


def print_summary_stats(df, title):
    """Calculates and prints summary statistics for a given dataframe."""
    if df.empty or df["rent_value"].notna().sum() == 0 or df["sqft_value"].notna().sum() == 0:
        print(f"\n--- {title} ---")
        print("No matching listings or missing rent/sqft data for stats.")
        return

    avg_rent = df["rent_value"].mean()
    min_rent = df["rent_value"].min()
    max_rent = df["rent_value"].max()
    avg_sqft = df["sqft_value"].mean()
    avg_rent_per_sqft = avg_rent / avg_sqft if avg_sqft and avg_sqft > 0 else None

    print(f"\n--- {title} ---")
    print(f"Listings matched: {len(df)}")
    print(f"Average Rent: ${avg_rent:,.0f}")
    print(f"Lowest Rent:  ${min_rent:,.0f}")
    print(f"Highest Rent: ${max_rent:,.0f}")
    if avg_rent_per_sqft:
        print(f"Average $/sqft: ${avg_rent_per_sqft:,.2f}")

def main():
    args = parse_args()

    try:
        df = pd.read_json(args.json_file)
    except Exception as e:
        print(f"Error reading {args.json_file}: {e}")
        sys.exit(1)

    # --- Data Preparation ---
    df["rent_value"] = df["rent"].apply(clean_numeric)
    df["sqft_value"] = df["sqft"].apply(clean_numeric)
    df[["bedrooms", "bathrooms"]] = df.apply(
        lambda row: pd.Series(extract_bed_bath(row["layout"])), axis=1
    )

    # --- Apply Filters Globally ---
    df_filtered = df.copy()
    bed_op, bed_val = parse_numeric_filter(args.bed)
    bath_op, bath_val = parse_numeric_filter(args.bath)
    
    df_filtered = apply_filter(df_filtered, "bedrooms", bed_op, bed_val)
    df_filtered = apply_filter(df_filtered, "bathrooms", bath_op, bath_val)

    if args.date:
        df_filtered = df_filtered[df_filtered["availability"].astype(str).str.contains(args.date, case=False, na=False)]
    
    # --- Iterate and Print by Property, collecting summary data ---
    pd.set_option("display.max_rows", None)
    pd.set_option("display.width", 200)
    pd.set_option("display.colheader_justify", "center")
    
    all_properties_summary = []

    for property_url, group in df.groupby('property_url'):
        print("\n" + "="*80)
        print(f"PROPERTY: {property_url}")
        print("="*80)

        # 1. Filtered Unit Details
        property_filtered_units = df_filtered[df_filtered['property_url'] == property_url]
        
        print("--- Filtered Unit Details ---")
        if not property_filtered_units.empty:
            display_cols = ["unit_number", "layout", "sqft", "availability", "rent"]
            print(property_filtered_units[display_cols].to_string(index=False))
        else:
            print("No units match the specified filters for this property.")

        # 2. Property Availability Summary
        total_units = group['total_property_units'].iloc[0]
        available_units_scraped = len(group)
        
        availability_pct_str = "N/A"
        percentage = None
        if pd.notna(total_units) and total_units > 0:
            percentage = (available_units_scraped / total_units) * 100
            availability_pct_str = f"{percentage:.1f}%"
        
        total_units_str = f"{total_units:.0f}" if pd.notna(total_units) else "N/A"

        print("\n--- Property Availability Summary ---")
        print(f"Total Units (from input): {total_units_str}")
        print(f"Available Units (on Zillow): {available_units_scraped}")
        print(f"Availability Pct: {availability_pct_str}")
        
        # 3. Summary stats for this Property
        print_summary_stats(property_filtered_units, "Summary for this Property")
        
        # --- Collect data for the final summary table ---
        avg_rent = property_filtered_units["rent_value"].mean()
        avg_sqft = property_filtered_units["sqft_value"].mean()
        avg_rent_per_sqft = avg_rent / avg_sqft if avg_sqft and avg_sqft > 0 else None

        all_properties_summary.append({
            "property_url": property_url,
            "total_units": total_units,
            "available_units": available_units_scraped,
            "availability_pct": percentage,
            "filtered_listings_count": len(property_filtered_units),
            "avg_rent": avg_rent,
            "avg_$/sqft": avg_rent_per_sqft
        })

    # --- Final Comparison Table ---
    print("\n" + "="*80)
    print("ALL PROPERTIES COMPARISON")
    print("="*80)

    summary_df = pd.DataFrame(all_properties_summary)

    # Formatting for display
    summary_df['total_units'] = summary_df['total_units'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "N/A")
    summary_df['availability_pct'] = summary_df['availability_pct'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A")
    summary_df['avg_rent'] = summary_df['avg_rent'].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "N/A")
    summary_df['avg_$/sqft'] = summary_df['avg_$/sqft'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A")

    print(summary_df.to_string(index=False))

if __name__ == "__main__":
    main()