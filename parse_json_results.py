import pandas as pd
import sys
import argparse
import re
import operator
import os

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


def get_summary_stats(df):
    """Calculates and returns a dictionary of summary statistics."""
    stats = {
        "listings_matched": len(df),
        "avg_rent": None,
        "min_rent": None,
        "max_rent": None,
        "avg_rent_per_sqft": None,
    }

    if not df.empty and df["rent_value"].notna().any() and df["sqft_value"].notna().any():
        stats["avg_rent"] = df["rent_value"].mean()
        stats["min_rent"] = df["rent_value"].min()
        stats["max_rent"] = df["rent_value"].max()
        avg_sqft = df["sqft_value"].mean()
        if avg_sqft and avg_sqft > 0:
            stats["avg_rent_per_sqft"] = stats["avg_rent"] / avg_sqft
            
    return stats


def print_summary_stats(stats, title):
    """Prints formatted summary statistics from a dictionary."""
    print(f"\n--- {title} ---")
    if stats["listings_matched"] == 0:
        print("No matching listings or missing rent/sqft data for stats.")
        return

    print(f"Listings matched: {stats['listings_matched']}")
    if stats['avg_rent'] is not None:
        print(f"Average Rent: ${stats['avg_rent']:,.0f}")
        print(f"Lowest Rent:  ${stats['min_rent']:,.0f}")
        print(f"Highest Rent: ${stats['max_rent']:,.0f}")
    if stats['avg_rent_per_sqft'] is not None:
        print(f"Average $/sqft: ${stats['avg_rent_per_sqft']:,.2f}")


def main():
    args = parse_args()

    # NEW: Determine output filename and redirect stdout
    output_filename = os.path.splitext(args.json_file)[0] + '.txt'
    original_stdout = sys.stdout
    
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            sys.stdout = f # Redirect print to file

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
            
            # --- Iterate and Print by Property ---
            pd.set_option("display.max_rows", None)
            pd.set_option("display.width", 200)
            pd.set_option("display.colheader_justify", "center")
            
            all_properties_summary_data = []

            for property_url, group in df.groupby('property_url'):
                print("\n" + "="*80)
                print(f"PROPERTY: {property_url}")
                print("="*80)

                # 1. Filtered Unit Details for this Property
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
                
                availability_pct = None
                if pd.notna(total_units) and total_units > 0:
                    availability_pct = (available_units_scraped / total_units) * 100
                
                total_units_str = f"{total_units:.0f}" if pd.notna(total_units) else "N/A"
                availability_pct_str = f"{availability_pct:.1f}%" if availability_pct is not None else "N/A"

                print("\n--- Property Availability Summary ---")
                print(f"Total Units (from input): {total_units_str}")
                print(f"Available Units (on Zillow): {available_units_scraped}")
                print(f"Availability Pct: {availability_pct_str}")
                
                # 3. Summary for this Property's Filtered Units
                property_stats = get_summary_stats(property_filtered_units)
                print_summary_stats(property_stats, "Summary for this Property")

                # 4. Collect data for final summary table
                all_properties_summary_data.append({
                    'property_url': property_url,
                    'total_units': total_units_str,
                    'available_units': available_units_scraped,
                    'availability_pct': availability_pct_str,
                    'filtered_units_count': property_stats['listings_matched'],
                    'avg_rent': f"${property_stats['avg_rent']:,.0f}" if property_stats['avg_rent'] is not None else "N/A",
                    'avg_rent_per_sqft': f"${property_stats['avg_rent_per_sqft']:,.2f}" if property_stats['avg_rent_per_sqft'] is not None else "N/A",
                })

            # --- Grand Total Summary ---
            print("\n" + "="*80)
            print("GRAND TOTAL SUMMARY (ALL PROPERTIES)")
            print("="*80)
            total_stats = get_summary_stats(df_filtered)
            print_summary_stats(total_stats, "Overall Summary (for all filtered results)")

            # --- All Properties Comparison Table ---
            if all_properties_summary_data:
                print("\n" + "="*80)
                print("ALL PROPERTIES COMPARISON")
                print("="*80)
                summary_df = pd.DataFrame(all_properties_summary_data)
                print(summary_df.to_string(index=False))

    finally:
        sys.stdout = original_stdout # Restore print to console

    # NEW: Print confirmation message to the console
    print(f"Output successfully saved to {output_filename}")


if __name__ == "__main__":
    main()