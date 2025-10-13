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
    if bed is None and isinstance(layout, str) and 'studio' in layout.lower():
        bed = 0
    return bed, bath


def apply_filter(df, col, op_func, value):
    """Apply operator-based filter."""
    if op_func and value is not None:
        if col in df.columns:
            valid_mask = pd.notna(df[col])
            df = df[valid_mask & df.loc[valid_mask, col].apply(lambda x: op_func(x, value))]
    return df


def get_summary_stats(df):
    """Calculates and returns a dictionary of summary statistics."""
    stats = {
        "listings_matched": len(df),
        "avg_rent": None, "min_rent": None, "max_rent": None,
        "avg_rent_per_sqft": None,
    }

    for i in range(4): # 0br (Studio) to 3br
        stats[f'avg_rent_per_sqft_{i}br'] = None

    if not df.empty and df["rent_value"].notna().any() and df["sqft_value"].notna().any():
        stats["avg_rent"] = df["rent_value"].mean()
        stats["min_rent"] = df["rent_value"].min()
        stats["max_rent"] = df["rent_value"].max()
        avg_sqft = df["sqft_value"].mean()
        if avg_sqft and avg_sqft > 0:
            stats["avg_rent_per_sqft"] = stats["avg_rent"] / avg_sqft
        
        for br_count in range(4): # 0, 1, 2, 3
            br_df = df[df['bedrooms'] == br_count]
            if not br_df.empty and br_df["rent_value"].notna().any() and br_df["sqft_value"].notna().any():
                br_avg_rent = br_df['rent_value'].mean()
                br_avg_sqft = br_df['sqft_value'].mean()
                if br_avg_sqft and br_avg_sqft > 0:
                    key = f'avg_rent_per_sqft_{br_count}br'
                    stats[key] = br_avg_rent / br_avg_sqft
            
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
    
    br_map = {0: 'Studio', 1: '1br', 2: '2br', 3: '3br'}
    for br_count, label in br_map.items():
        key = f'avg_rent_per_sqft_{br_count}br'
        if stats.get(key) is not None:
            print(f"Average $/sqft ({label}): ${stats[key]:,.2f}")


def main():
    args = parse_args()

    output_filename = os.path.splitext(args.json_file)[0] + '.txt'
    original_stdout = sys.stdout
    
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            sys.stdout = f

            try:
                df = pd.read_json(args.json_file)
            except Exception as e:
                print(f"Error reading {args.json_file}: {e}")
                sys.exit(1)

            df["rent_value"] = df["rent"].apply(clean_numeric)
            df["sqft_value"] = df["sqft"].apply(clean_numeric)
            df[["bedrooms", "bathrooms"]] = df.apply(
                lambda row: pd.Series(extract_bed_bath(row["layout"])), axis=1
            )

            df_filtered = df.copy()
            bed_op, bed_val = parse_numeric_filter(args.bed)
            bath_op, bath_val = parse_numeric_filter(args.bath)
            
            df_filtered = apply_filter(df_filtered, "bedrooms", bed_op, bed_val)
            df_filtered = apply_filter(df_filtered, "bathrooms", bath_op, bath_val)

            if args.date:
                df_filtered = df_filtered[df_filtered["availability"].astype(str).str.contains(args.date, case=False, na=False)]
            
            pd.set_option("display.max_rows", None)
            pd.set_option("display.width", 200)
            pd.set_option("display.colheader_justify", "center")
            
            all_properties_summary_data = []
            sorted_property_urls = sorted(df['property_url'].unique())

            for property_url in sorted_property_urls:
                group = df[df['property_url'] == property_url]
                print("\n" + "="*80)
                print(f"PROPERTY: {property_url}")
                print("="*80)

                property_filtered_units = df_filtered[df_filtered['property_url'] == property_url]
                
                print("--- Filtered Unit Details ---")
                if not property_filtered_units.empty:
                    property_filtered_units = property_filtered_units.sort_values(
                        by=['bedrooms', 'unit_number'], na_position='last'
                    )
                    display_cols = ["unit_number", "layout", "sqft", "availability", "rent"]
                    print(property_filtered_units[display_cols].to_string(index=False))
                else:
                    print("No units match the specified filters for this property.")

                if 'total_property_units' in group.columns:
                    total_units = group['total_property_units'].iloc[0]
                else:
                    total_units = None

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
                
                property_stats = get_summary_stats(property_filtered_units)
                print_summary_stats(property_stats, "Summary for this Property")

                summary_entry = {
                    'property_url': property_url,
                    'total_units': total_units_str,
                    'available_units': available_units_scraped,
                    'availability_pct': availability_pct_str,
                    'filtered_units_count': property_stats['listings_matched'],
                    'avg_rent': f"${property_stats['avg_rent']:,.0f}" if property_stats['avg_rent'] is not None else "N/A",
                    'avg_$/sqft': f"${property_stats['avg_rent_per_sqft']:,.2f}" if property_stats['avg_rent_per_sqft'] is not None else "N/A",
                }
                for i in range(4):
                    key = f'avg_rent_per_sqft_{i}br'
                    col_name = f'avg_$/sqft_{i}br'
                    value = property_stats.get(key)
                    summary_entry[col_name] = f"${value:,.2f}" if value is not None else "N/A"
                
                # NEW: Add a raw numeric value for sorting the final table
                summary_entry['_sort_val_2br_sqft'] = property_stats.get('avg_rent_per_sqft_2br')
                all_properties_summary_data.append(summary_entry)

            print("\n" + "="*80)
            print("GRAND TOTAL SUMMARY (ALL PROPERTIES)")
            print("="*80)
            total_stats = get_summary_stats(df_filtered)
            print_summary_stats(total_stats, "Overall Summary (for all filtered results)")

            if all_properties_summary_data:
                print("\n" + "="*80)
                print("ALL PROPERTIES COMPARISON")
                print("="*80)
                summary_df = pd.DataFrame(all_properties_summary_data)
                
                # NEW: Sort the DataFrame by the 2-bedroom $/sqft value
                if '_sort_val_2br_sqft' in summary_df.columns:
                    summary_df = summary_df.sort_values(by='_sort_val_2br_sqft', ascending=True, na_position='last')
                    # Drop the temporary sort column so it is not printed
                    summary_df = summary_df.drop(columns=['_sort_val_2br_sqft'])
                
                print(summary_df.to_string(index=False))

    finally:
        sys.stdout = original_stdout

    print(f"Output successfully saved to {output_filename}")


if __name__ == "__main__":
    main()