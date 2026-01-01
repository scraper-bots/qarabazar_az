#!/usr/bin/env python3
"""
Business Intelligence Dashboard - qarabazar.az Real Estate Market Analysis
Generates actionable visualizations for executive decision-making.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Configure professional styling
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 7)
plt.rcParams['font.size'] = 10
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 11

# Define output directory
OUTPUT_DIR = Path("charts")
OUTPUT_DIR.mkdir(exist_ok=True)

def load_and_prepare_data(csv_path):
    """Load and clean the dataset for analysis."""
    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)

    # Clean and prepare data
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df['area_sqm'] = pd.to_numeric(df['area_sqm'], errors='coerce')
    df['price_per_sqm'] = pd.to_numeric(df['price_per_sqm'], errors='coerce')
    df['rooms_numeric'] = pd.to_numeric(df['rooms_numeric'], errors='coerce')
    df['floor_numeric'] = pd.to_numeric(df['floor_numeric'], errors='coerce')

    # Remove outliers (prices beyond reasonable range)
    df = df[df['price'].between(1000, 10_000_000)]

    print(f"Loaded {len(df)} valid listings")
    return df

def chart_1_market_overview(df):
    """Market Segmentation: Inventory Distribution by Property Type and Transaction"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Property type distribution
    property_counts = df['property_type'].value_counts()
    colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D']
    ax1.barh(property_counts.index, property_counts.values, color=colors[:len(property_counts)])
    ax1.set_xlabel('Number of Listings', fontweight='bold')
    ax1.set_title('Inventory by Property Type', fontweight='bold', fontsize=13)
    ax1.grid(axis='x', alpha=0.3)

    # Add value labels
    for i, v in enumerate(property_counts.values):
        ax1.text(v, i, f' {v}', va='center', fontweight='bold')

    # Transaction type distribution
    trans_counts = df['transaction_type'].value_counts()
    ax2.barh(trans_counts.index, trans_counts.values, color=['#06A77D', '#005377', '#F77F00'])
    ax2.set_xlabel('Number of Listings', fontweight='bold')
    ax2.set_title('Inventory by Transaction Type', fontweight='bold', fontsize=13)
    ax2.grid(axis='x', alpha=0.3)

    # Add value labels
    for i, v in enumerate(trans_counts.values):
        ax2.text(v, i, f' {v}', va='center', fontweight='bold')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / '01_market_overview.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: Market Overview")
    plt.close()

def chart_2_price_analysis_by_type(df):
    """Price Analysis: Average Pricing by Property Type"""
    property_prices = df.groupby('property_type').agg({
        'price': ['mean', 'median', 'count']
    }).round(0)
    property_prices.columns = ['Average Price', 'Median Price', 'Count']
    property_prices = property_prices.sort_values('Average Price', ascending=False)

    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(property_prices))
    width = 0.35

    bars1 = ax.bar(x - width/2, property_prices['Average Price'], width,
                   label='Average', color='#2E86AB', alpha=0.8)
    bars2 = ax.bar(x + width/2, property_prices['Median Price'], width,
                   label='Median', color='#A23B72', alpha=0.8)

    ax.set_xlabel('Property Type', fontweight='bold')
    ax.set_ylabel('Price (AZN)', fontweight='bold')
    ax.set_title('Average vs Median Pricing by Property Type', fontweight='bold', fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(property_prices.index, rotation=0)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height/1000)}K',
                   ha='center', va='bottom', fontsize=9, fontweight='bold')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / '02_price_by_property_type.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: Price Analysis by Property Type")
    plt.close()

def chart_3_price_distribution(df):
    """Price Distribution: Understanding Market Price Ranges"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    property_types = ['apartment', 'house', 'land', 'commercial']
    colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D']

    for idx, (ptype, color) in enumerate(zip(property_types, colors)):
        ax = axes[idx // 2, idx % 2]
        data = df[df['property_type'] == ptype]['price'].dropna()

        if len(data) > 0:
            ax.hist(data, bins=30, color=color, alpha=0.7, edgecolor='black')
            ax.axvline(data.mean(), color='red', linestyle='--', linewidth=2, label=f'Avg: {int(data.mean()):,} AZN')
            ax.axvline(data.median(), color='green', linestyle='--', linewidth=2, label=f'Median: {int(data.median()):,} AZN')
            ax.set_xlabel('Price (AZN)', fontweight='bold')
            ax.set_ylabel('Number of Listings', fontweight='bold')
            ax.set_title(f'{ptype.title()} Price Distribution', fontweight='bold')
            ax.legend()
            ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / '03_price_distribution.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: Price Distribution Analysis")
    plt.close()

def chart_4_location_insights(df):
    """Location Intelligence: Top Markets by Volume and Average Price"""
    # Filter for cities/districts with at least 10 listings
    location_stats = df.groupby('city').agg({
        'price': ['mean', 'count']
    })
    location_stats.columns = ['avg_price', 'count']
    location_stats = location_stats[location_stats['count'] >= 10].sort_values('count', ascending=False).head(15)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    # Top locations by volume
    ax1.barh(location_stats.index, location_stats['count'], color='#06A77D')
    ax1.set_xlabel('Number of Listings', fontweight='bold')
    ax1.set_title('Top 15 Locations by Inventory Volume', fontweight='bold', fontsize=13)
    ax1.grid(axis='x', alpha=0.3)

    for i, v in enumerate(location_stats['count'].values):
        ax1.text(v, i, f' {int(v)}', va='center', fontweight='bold')

    # Average price by top locations
    price_sorted = location_stats.sort_values('avg_price', ascending=False)
    ax2.barh(price_sorted.index, price_sorted['avg_price'], color='#2E86AB')
    ax2.set_xlabel('Average Price (AZN)', fontweight='bold')
    ax2.set_title('Average Price by Location (Top 15 Markets)', fontweight='bold', fontsize=13)
    ax2.grid(axis='x', alpha=0.3)

    for i, v in enumerate(price_sorted['avg_price'].values):
        ax2.text(v, i, f' {int(v/1000)}K', va='center', fontweight='bold')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / '04_location_insights.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: Location Intelligence")
    plt.close()

def chart_5_price_per_sqm_analysis(df):
    """Unit Economics: Price per Square Meter by Property Type"""
    ppsm_data = df[df['price_per_sqm'].notna() & (df['price_per_sqm'] > 0) & (df['price_per_sqm'] < 20000)]

    fig, ax = plt.subplots(figsize=(12, 7))

    property_types = ppsm_data['property_type'].unique()
    positions = []
    labels = []

    for i, ptype in enumerate(property_types):
        data = ppsm_data[ppsm_data['property_type'] == ptype]['price_per_sqm']
        if len(data) > 5:
            positions.append(data)
            labels.append(f'{ptype.title()}\n(n={len(data)})')

    bp = ax.boxplot(positions, labels=labels, patch_artist=True,
                    showmeans=True, meanline=True)

    colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D']
    for patch, color in zip(bp['boxes'], colors[:len(positions)]):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_ylabel('Price per Square Meter (AZN/sqm)', fontweight='bold')
    ax.set_title('Unit Economics: Price per sqm Distribution by Property Type', fontweight='bold', fontsize=14)
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / '05_price_per_sqm.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: Price per Sqm Analysis")
    plt.close()

def chart_6_apartment_insights(df):
    """Apartment Market: Room Configuration and Floor Level Analysis"""
    apartments = df[df['property_type'] == 'apartment'].copy()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Room distribution
    room_counts = apartments['rooms_numeric'].value_counts().sort_index()
    ax1.bar(room_counts.index, room_counts.values, color='#2E86AB', alpha=0.8)
    ax1.set_xlabel('Number of Rooms', fontweight='bold')
    ax1.set_ylabel('Number of Listings', fontweight='bold')
    ax1.set_title('Apartment Inventory by Room Count', fontweight='bold', fontsize=13)
    ax1.grid(axis='y', alpha=0.3)

    for i, v in enumerate(room_counts.values):
        ax1.text(room_counts.index[i], v, f'{v}', ha='center', va='bottom', fontweight='bold')

    # Average price by rooms
    room_prices = apartments.groupby('rooms_numeric')['price'].mean().sort_index()
    ax2.plot(room_prices.index, room_prices.values, marker='o', linewidth=2,
             markersize=8, color='#A23B72')
    ax2.set_xlabel('Number of Rooms', fontweight='bold')
    ax2.set_ylabel('Average Price (AZN)', fontweight='bold')
    ax2.set_title('Average Apartment Price by Room Count', fontweight='bold', fontsize=13)
    ax2.grid(alpha=0.3)

    for x, y in zip(room_prices.index, room_prices.values):
        ax2.text(x, y, f'{int(y/1000)}K', ha='center', va='bottom', fontweight='bold')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / '06_apartment_insights.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: Apartment Market Insights")
    plt.close()

def chart_7_seller_analysis(df):
    """Market Dynamics: Agent vs Owner Listings"""
    seller_stats = df.groupby('seller_category').agg({
        'price': ['mean', 'median', 'count']
    })
    seller_stats.columns = ['avg_price', 'median_price', 'count']
    seller_stats = seller_stats.sort_values('count', ascending=False)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Volume by seller type
    ax1.bar(seller_stats.index, seller_stats['count'], color=['#06A77D', '#F18F01'], alpha=0.8)
    ax1.set_ylabel('Number of Listings', fontweight='bold')
    ax1.set_title('Listing Volume by Seller Category', fontweight='bold', fontsize=13)
    ax1.grid(axis='y', alpha=0.3)

    for i, (idx, row) in enumerate(seller_stats.iterrows()):
        ax1.text(i, row['count'], f"{int(row['count'])}", ha='center', va='bottom', fontweight='bold')

    # Price comparison
    x = np.arange(len(seller_stats))
    width = 0.35
    ax2.bar(x - width/2, seller_stats['avg_price'], width, label='Average', color='#2E86AB', alpha=0.8)
    ax2.bar(x + width/2, seller_stats['median_price'], width, label='Median', color='#A23B72', alpha=0.8)
    ax2.set_ylabel('Price (AZN)', fontweight='bold')
    ax2.set_title('Price Comparison by Seller Category', fontweight='bold', fontsize=13)
    ax2.set_xticks(x)
    ax2.set_xticklabels(seller_stats.index)
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / '07_seller_analysis.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: Seller Market Analysis")
    plt.close()

def chart_8_area_analysis(df):
    """Property Size Analysis: Area Distribution by Type"""
    area_data = df[df['area_sqm'].notna() & (df['area_sqm'] > 0) & (df['area_sqm'] < 1000)]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    property_types = ['apartment', 'house', 'commercial', 'land']
    colors = ['#2E86AB', '#A23B72', '#C73E1D', '#F18F01']

    for idx, (ptype, color) in enumerate(zip(property_types, colors)):
        ax = axes[idx // 2, idx % 2]
        data = area_data[area_data['property_type'] == ptype]['area_sqm'].dropna()

        if len(data) > 0:
            ax.hist(data, bins=25, color=color, alpha=0.7, edgecolor='black')
            ax.axvline(data.mean(), color='red', linestyle='--', linewidth=2,
                      label=f'Avg: {int(data.mean())} sqm')
            ax.axvline(data.median(), color='green', linestyle='--', linewidth=2,
                      label=f'Median: {int(data.median())} sqm')
            ax.set_xlabel('Area (sqm)', fontweight='bold')
            ax.set_ylabel('Number of Listings', fontweight='bold')
            ax.set_title(f'{ptype.title()} Size Distribution', fontweight='bold')
            ax.legend()
            ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / '08_area_analysis.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: Property Size Analysis")
    plt.close()

def chart_9_rent_vs_sale(df):
    """Transaction Analysis: Rental vs Sales Market Comparison"""
    rent_sale = df[df['transaction_type'].isin(['rent', 'sale'])].copy()

    if len(rent_sale) == 0:
        print("⚠ Insufficient data for rent vs sale analysis")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Volume by property type
    trans_prop = pd.crosstab(rent_sale['property_type'], rent_sale['transaction_type'])
    trans_prop.plot(kind='bar', ax=ax1, color=['#06A77D', '#2E86AB'], alpha=0.8)
    ax1.set_xlabel('Property Type', fontweight='bold')
    ax1.set_ylabel('Number of Listings', fontweight='bold')
    ax1.set_title('Rental vs Sales Volume by Property Type', fontweight='bold', fontsize=13)
    ax1.legend(title='Transaction Type', labels=['Rent', 'Sale'])
    ax1.grid(axis='y', alpha=0.3)
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # Price comparison for apartments only
    apt_trans = rent_sale[rent_sale['property_type'] == 'apartment']
    if len(apt_trans) > 0:
        trans_prices = apt_trans.groupby('transaction_type')['price'].mean()
        ax2.bar(trans_prices.index, trans_prices.values, color=['#06A77D', '#2E86AB'], alpha=0.8)
        ax2.set_ylabel('Average Price (AZN)', fontweight='bold')
        ax2.set_title('Average Apartment Pricing: Rent vs Sale', fontweight='bold', fontsize=13)
        ax2.grid(axis='y', alpha=0.3)

        for i, v in enumerate(trans_prices.values):
            ax2.text(i, v, f'{int(v/1000)}K', ha='center', va='bottom', fontweight='bold')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / '09_rent_vs_sale.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: Rent vs Sale Analysis")
    plt.close()

def chart_10_market_heatmap(df):
    """Market Positioning: Price vs Area Scatter Analysis"""
    # Focus on apartments with valid price and area
    scatter_data = df[(df['property_type'] == 'apartment') &
                      (df['price'].notna()) &
                      (df['area_sqm'].notna()) &
                      (df['area_sqm'] > 20) &
                      (df['area_sqm'] < 300) &
                      (df['price'] > 10000) &
                      (df['price'] < 1000000)].copy()

    fig, ax = plt.subplots(figsize=(12, 8))

    # Color by rooms if available
    if 'rooms_numeric' in scatter_data.columns:
        scatter = ax.scatter(scatter_data['area_sqm'], scatter_data['price'],
                           c=scatter_data['rooms_numeric'], cmap='viridis',
                           alpha=0.6, s=50, edgecolors='black', linewidth=0.5)
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('Number of Rooms', fontweight='bold')
    else:
        ax.scatter(scatter_data['area_sqm'], scatter_data['price'],
                  alpha=0.6, s=50, color='#2E86AB', edgecolors='black', linewidth=0.5)

    ax.set_xlabel('Area (sqm)', fontweight='bold')
    ax.set_ylabel('Price (AZN)', fontweight='bold')
    ax.set_title('Apartment Market Positioning: Price vs Size', fontweight='bold', fontsize=14)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / '10_market_positioning.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: Market Positioning Analysis")
    plt.close()

def generate_summary_stats(df):
    """Generate key business metrics summary"""
    summary = {
        'Total Listings': len(df),
        'Avg Price (AZN)': f"{int(df['price'].mean()):,}",
        'Median Price (AZN)': f"{int(df['price'].median()):,}",
        'Price Range': f"{int(df['price'].min()):,} - {int(df['price'].max()):,}",
        'Most Common Property': df['property_type'].mode()[0],
        'Most Active Location': df['city'].mode()[0],
        'Agent vs Owner': f"{len(df[df['seller_category']=='agent'])} / {len(df[df['seller_category']=='owner'])}",
        'Avg Area (sqm)': f"{int(df['area_sqm'].mean())}" if df['area_sqm'].notna().any() else 'N/A'
    }

    print("\n" + "="*60)
    print("MARKET SUMMARY STATISTICS")
    print("="*60)
    for key, value in summary.items():
        print(f"{key:.<40} {value:>18}")
    print("="*60 + "\n")

    return summary

def main():
    """Main execution function"""
    print("\n" + "="*60)
    print("QARABAZAR.AZ REAL ESTATE MARKET ANALYSIS")
    print("Business Intelligence Dashboard Generator")
    print("="*60 + "\n")

    # Find the most recent CSV file
    csv_files = list(Path("scraped_data").glob("listings_*.csv"))
    if not csv_files:
        print("ERROR: No CSV files found in scraped_data/")
        return

    latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)
    print(f"Using data file: {latest_csv.name}\n")

    # Load and prepare data
    df = load_and_prepare_data(latest_csv)

    # Generate summary statistics
    summary = generate_summary_stats(df)

    # Generate all charts
    print("Generating business intelligence visualizations...\n")

    chart_1_market_overview(df)
    chart_2_price_analysis_by_type(df)
    chart_3_price_distribution(df)
    chart_4_location_insights(df)
    chart_5_price_per_sqm_analysis(df)
    chart_6_apartment_insights(df)
    chart_7_seller_analysis(df)
    chart_8_area_analysis(df)
    chart_9_rent_vs_sale(df)
    chart_10_market_heatmap(df)

    print("\n" + "="*60)
    print(f"SUCCESS: All visualizations generated in '{OUTPUT_DIR}/' directory")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
