# -*- coding: utf-8 -*-
#
# Copyright (c) 2025 Stephen Li
#
# File: analyze_zillow_data.py
# Author: Stephen Li
#
# Description: This script analyzes the scraped Zillow data from a JSON file
#              and generates a detailed text report.
#
# This tool is provided for free for individual, personal use.
#

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
        bed = 1
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
        "avg_rent_per_sqft": None, "avg_sqft": None
    }

    for i in range(1, 4):
        stats[f'avg_rent_per_sqft_{i}br'] = None
        stats[f'avg_sqft_{i}br'] = None
        stats[f'min_rent_{i}br'] = None
        stats[f'avg_rent_{i}br'] = None
        stats[f'max_rent_{i}br'] = None
        # NEW: Keys for sqft of min and max rent units
        stats[f'min_rent_sqft_{i}br'] = None
        stats[f'max_rent_sqft_{i}br'] = None

    if not df.empty and df["rent_value"].notna().any():
        stats["avg_rent"] = df["rent_value"].mean()
        stats["min_rent"] = df["rent_value"].min()
        stats["max_rent"] = df["rent_value"].max()
        if df["sqft_value"].notna().any():
            avg_sqft = df["sqft_value"].mean()
            stats["avg_sqft"] = avg_sqft
            if avg_sqft and avg_sqft > 0:
                stats["avg_rent_per_sqft"] = stats["avg_rent"] / avg_sqft
        
        for br_count in range(1, 4):
            br_df = df[(df['bedrooms'] == br_count) & (df['rent_value'].notna())]
            if not br_df.empty:
                # NEW: Find the full rows for min and max rent to get their specific sqft
                min_rent_row = br_df.loc[br_df['rent_value'].idxmin()]
                max_rent_row = br_df.loc[br_df['rent_value'].idxmax()]

                stats[f'min_rent_{br_count}br'] = min_rent_row['rent_value']
                stats[f'min_rent_sqft_{br_count}br'] = min_rent_row['sqft_value']

                stats[f'max_rent_{br_count}br'] = max_rent_row['rent_value']
                stats[f'max_rent_sqft_{br_count}br'] = max_rent_row['sqft_value']
                
                stats[f'avg_rent_{br_count}br'] = br_df['rent_value'].mean()

                if br_df["sqft_value"].notna().any():
                    br_avg_sqft = br_df['sqft_value'].mean()
                    if br_avg_sqft and br_avg_sqft > 0:
                        stats[f'avg_sqft_{br_count}br'] = br_avg_sqft
                        stats[f'avg_rent_per_sqft_{br_count}br'] = stats[f'avg_rent_{br_count}br'] / br_avg_sqft
            
    return stats


def print_summary_stats(stats, title):
    """Prints formatted summary statistics from a dictionary."""
    print(f"\n--- {title} ---")
    if stats["listings_matched"] == 0:
        print("No matching listings or missing rent/sqft data for stats.")
        return

    print(f"Listings matched: {stats['listings_matched']}")
    
    br_map = {1: '1 bedroom', 2: '2 bedroom', 3: '3 bedroom'}
    for br_count, label in br_map.items():
        min_rent_key = f'min_rent_{br_count}br'
        
        if stats.get(min_rent_key) is not None:
            # Lowest
            min_r = stats[min_rent_key]
            min_s = stats.get(f'min_rent_sqft_{br_count}br')
            min_psf_str = "N/A"
            if pd.notna(min_s) and min_s > 0:
                min_psf_str = f"${min_r / min_s:,.2f}"
            lowest_str = f"${min_r:,.0f} @ {min_psf_str}"

            # Average
            avg_r = stats[f'avg_rent_{br_count}br']
            avg_s = stats.get(f'avg_sqft_{br_count}br')
            avg_psf_str = "N/A"
            if pd.notna(avg_s) and avg_s > 0:
                avg_psf_str = f"${avg_r / avg_s:,.2f}"
            avg_str = f"${avg_r:,.0f} @ {avg_psf_str}"

            # Highest
            max_r = stats[f'max_rent_{br_count}br']
            max_s = stats.get(f'max_rent_sqft_{br_count}br')
            max_psf_str = "N/A"
            if pd.notna(max_s) and max_s > 0:
                max_psf_str = f"${max_r / max_s:,.2f}"
            highest_str = f"${max_r:,.0f} @ {max_psf_str}"
            
            print(f"Lowest-Average-Highest Rent for {label}: {lowest_str}, {avg_str}, {highest_str}")


def main():
    args = parse_args()

    output_filename = os.path.splitext(args.json_file)[0] + '.txt'
    original_stdout = sys.stdout
    
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            sys.stdout = f

            BANNER = """
=======================================================================
 Zillow Market Analysis Report
 Copyright (c) 2025 Stephen Li

 This report is generated by the Zillow Unit WebScraper tool.
 This tool is provided for free for individual, personal use.
=======================================================================
"""
            print(BANNER)

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
                now_units = group['availability'].str.contains('Now', case=False, na=False).sum()
                
                availability_pct = None
                if pd.notna(total_units) and total_units > 0:
                    availability_pct = (available_units_scraped / total_units) * 100
                total_units_str = f"{total_units:.0f}" if pd.notna(total_units) else "N/A"
                availability_pct_str = f"{availability_pct:.1f}%" if availability_pct is not None else "N/A"

                print("\n--- Property Availability Summary ---")
                print(f"Total Units (from input): {total_units_str}")
                print(f"Available Units (on Zillow): {available_units_scraped}")
                print(f"Available Now Units: {now_units}")
                print(f"Availability Pct: {availability_pct_str}")
                
                property_stats = get_summary_stats(property_filtered_units)
                print_summary_stats(property_stats, "Summary for this Property (based on filtered results)")

                summary_entry = {
                    'property_url': property_url,
                    'total_units': total_units_str,
                    'available_units': available_units_scraped,
                    'available_now': now_units,
                    'availability_pct': availability_pct_str,
                    'filtered_units_count': property_stats['listings_matched'],
                }
                
                avg_rent_val = property_stats.get('avg_rent_per_sqft')
                avg_sqft_val = property_stats.get('avg_sqft')
                if avg_rent_val is not None and avg_sqft_val is not None:
                    summary_entry['avg_value'] = f"${avg_rent_val:,.2f} @ {avg_sqft_val:,.0f} sqft"
                else:
                    summary_entry['avg_value'] = "N/A"

                for i in range(1, 4):
                    rent_key = f'avg_rent_per_sqft_{i}br'
                    sqft_key = f'avg_sqft_{i}br'
                    col_name = f'value_{i}br'
                    rent_val = property_stats.get(rent_key)
                    sqft_val = property_stats.get(sqft_key)
                    if rent_val is not None and sqft_val is not None:
                        summary_entry[col_name] = f"${rent_val:,.2f} @ {sqft_val:,.0f} sqft"
                    else:
                        summary_entry[col_name] = "N/A"
                
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
                
                if '_sort_val_2br_sqft' in summary_df.columns:
                    summary_df = summary_df.sort_values(by='_sort_val_2br_sqft', ascending=True, na_position='last')
                    summary_df = summary_df.drop(columns=['_sort_val_2br_sqft'])
                
                print(summary_df.to_string(index=False))

    finally:
        sys.stdout = original_stdout

    print(f"Output successfully saved to {output_filename}")


if __name__ == "__main__":
    main()
