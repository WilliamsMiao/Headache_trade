import json
import glob
import pandas as pd
import os
import re
import sys

def calculate_drawdown(trades, initial_balance):
    balance = initial_balance
    peak = balance
    max_dd = 0
    
    for trade in trades:
        # Assuming 'pnl_usdt' matches the trade key in your json files
        balance += trade.get('pnl_usdt', 0)
        
        if balance > peak:
            peak = balance
            
        if peak != 0:
            dd = (peak - balance) / peak
        else:
            dd = 0
            
        if dd > max_dd:
            max_dd = dd
            
    return max_dd * 100

def main():
    # Glob pattern for backtest reports
    # The user's workspace shows 'data/backtest/reports/' containing result JSONs
    files = glob.glob('data/backtest/reports/backtest_results_*.json')
    
    results = []
    
    print(f"Found {len(files)} backtest result files.")
    
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract metrics
            total_return_pct = data.get('total_return_pct', 0)
            win_rate = data.get('win_rate', 0)
            total_trades = data.get('total_trades', 0)
            initial_balance = data.get('initial_balance', 0)
            trades = data.get('trades', [])
            sharpe_ratio = data.get('sharpe_ratio', 0) # Attempt to get sharpe if available
            
            # Extract config_file from filename
            filename = os.path.basename(file_path)
            # Remove prefix
            if filename.startswith('backtest_results_'):
                config_name = filename[len('backtest_results_'):]
            else:
                config_name = filename
                
            # Remove suffix
            if config_name.endswith('.json'):
                config_name = config_name[:-5]
            
            # Reconstruct the likely config file path for reference
            # Files are in data/backtest/configs/
            config_file_path = f"data/backtest/configs/{config_name}.json"
            
            # Calculate Max Drawdown
            max_dd = calculate_drawdown(trades, initial_balance)
            
            results.append({
                'config_name': config_name,
                'total_return_pct': total_return_pct,
                'win_rate': win_rate,
                'total_trades': total_trades,
                'max_drawdown_pct': max_dd,
                'path': config_file_path
            })
            
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            continue
            
    # Create DataFrame
    if results:
        df = pd.DataFrame(results)
        
        # Sort by total_return_pct descending
        df = df.sort_values(by='total_return_pct', ascending=False)
        
        # Save to csv
        output_csv = 'data/backtest_summary.csv'
        
        # Ensure directory exists (it should, but good practice)
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        
        df.to_csv(output_csv, index=False)
        print(f"Summary saved to {output_csv}")
        
        # Print top 5
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        pd.set_option('display.max_colwidth', 50) # Truncate long names slightly for display
        print("\n=== Top 5 Performing Strategies ===")
        print(df[['config_name', 'total_return_pct', 'win_rate', 'max_drawdown_pct', 'total_trades']].head(5).to_string(index=False))
    else:
        print("No results to process.")

if __name__ == "__main__":
    main()
