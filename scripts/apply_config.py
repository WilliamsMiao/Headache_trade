import json
import pandas as pd
import os
import sys
import re
import glob

def update_env_file(settings):
    """
    Update .env file with provided settings.
    Preserves comments and existing structure.
    """
    env_path = '.env'
    try:
        if not os.path.exists(env_path):
            print(f"Creating new {env_path} file.")
            with open(env_path, 'w') as f:
                f.write("") # Create empty file
        
        with open(env_path, 'r') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading .env file: {e}")
        return

    updated_keys = set()
    new_lines = []
    
    # Process existing lines
    for line in lines:
        match = re.match(r'^\s*([A-Z_]+)\s*=', line)
        if match:
            key = match.group(1)
            if key in settings:
                # Update value
                value = settings[key]
                new_lines.append(f"{key}={value}\n")
                updated_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # Append new keys
    added_count = 0
    remaining_keys = [k for k in settings if k not in updated_keys]
    
    if remaining_keys:
        # Check if we need a newline before appending
        if new_lines and len(new_lines) > 0 and not new_lines[-1].endswith('\n'):
            new_lines.append('\n')
            
        # Add a section header if there are new keys
        new_lines.append("\n# === Auto-applied Backtest Configuration ===\n")
            
        for key in remaining_keys:
            value = settings[key]
            new_lines.append(f"{key}={value}\n")
            added_count += 1
            updated_keys.add(key)

    try:
        with open(env_path, 'w') as f:
            f.writelines(new_lines)
        print(f"✅ Successfully updated .env: {len(settings)} variables processed ({len(settings) - added_count} updated, {added_count} added).")
    except Exception as e:
        print(f"Error writing to .env file: {e}")

def main():
    summary_path = 'data/backtest_summary.csv'
    if not os.path.exists(summary_path):
        print(f"Error: {summary_path} not found. Run analyze_backtest_results.py first.")
        return

    df = pd.read_csv(summary_path)
    
    # Filter for strategies with at least 10 trades to ensure robustness
    robust_df = df[df['total_trades'] >= 10]
    
    if robust_df.empty:
        print("No robust strategies (>= 10 trades) found. Falling back to top return regardless of trade count.")
        best_row = df.iloc[0]
    else:
        # Pick top return among robust ones
        best_row = robust_df.iloc[0]
        
    config_name = best_row['config_name']
    total_return = best_row['total_return_pct']
    trades = best_row['total_trades']
    
    print(f"Selecting best strategy: {config_name}")
    print(f"Metrics: Return={total_return:.2f}%, Trades={trades}, WinRate={best_row['win_rate']:.2f}%")
    
    # Locate config file
    if 'path' in best_row and pd.notna(best_row['path']) and os.path.exists(str(best_row['path'])):
        config_path = best_row['path']
    else: 
        # Strategy name often contains timestamp suffixes from reports
        base_name = str(config_name)
        timestamp_pattern = r'_\d{8}_\d{6}'
        base_name_clean = re.sub(timestamp_pattern, '', base_name)
        
        candidates = [
            f"data/backtest/configs/{config_name}.json",
            f"data/backtest/configs/{base_name_clean}.json",
        ]
        
        config_path = None
        for candidate in candidates:
            if os.path.exists(candidate):
                config_path = candidate
                break
        
        if not config_path:
             # Fallback: exact match in directory via glob
            print(f"Warning: Specific config not found for {config_name}. Searching...")
            matches = glob.glob(f"data/backtest/configs/*{base_name_clean}*.json")
            if matches:
                matches.sort(key=len)
                config_path = matches[0]
            else:
                print(f"Error: Config file not found for {config_name}.")
                return

    print(f"Reading config from: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error reading config: {e}")
        return

    # Prepare settings dict
    settings = {}
    
    # Mapping
    keys_map = {
        'sl_multiplier_high': 'SL_MULTIPLIER_HIGH',
        'tp_multiplier_high': 'TP_MULTIPLIER_HIGH',
        'sl_multiplier_mid': 'SL_MULTIPLIER_MID',
        'tp_multiplier_mid': 'TP_MULTIPLIER_MID',
        'sl_multiplier_low': 'SL_MULTIPLIER_LOW',
        'tp_multiplier_low': 'TP_MULTIPLIER_LOW',
        'trend_score_entry': 'TREND_SCORE_ENTRY',
        'funding_abs_max': 'FUNDING_ABS_MAX',
        'rsi_long_min': 'RSI_LONG_MIN',
        'rsi_short_max': 'RSI_SHORT_MAX',
        'rsi_overbought': 'RSI_OVERBOUGHT',
        'rsi_oversold': 'RSI_OVERSOLD',
        'leverage': 'BOT_LEVERAGE'
    }
    
    for json_key, env_var in keys_map.items():
        if json_key in config:
            settings[env_var] = config[json_key]
        else:
            # Check for aliases
            if json_key == 'rsi_overbought' and 'rsi_extreme_high' in config:
                 settings[env_var] = config['rsi_extreme_high']
            elif json_key == 'rsi_oversold' and 'rsi_extreme_low' in config:
                 settings[env_var] = config['rsi_extreme_low']

    print("\nApplying the following settings to .env:")
    for k, v in settings.items():
        print(f"{k}={v}")
        
    update_env_file(settings)

if __name__ == "__main__":
    main()
