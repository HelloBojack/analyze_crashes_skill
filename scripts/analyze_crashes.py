#!/usr/bin/env python3
"""
Stock Crash Analyzer - 股票暴跌分析器
支持任意股票代码，生成交互式 HTML 分析报告

用法:
    python analyze_crashes.py --stock AAPL --benchmark QQQ --start 2021-01-01 --end 2026-06-26 --threshold 2.0 --output report.html

参数:
    --stock:      目标股票代码（如 AAPL, TSLA, NVDA）
    --benchmark:  对比指数（如 QQQ, SPY, IXIC）
    --start:      开始日期（YYYY-MM-DD）
    --end:        结束日期（YYYY-MM-DD）
    --threshold:  暴跌阈值（百分比，默认 2.0）
    --output:     输出 HTML 文件路径
    --events:     可选：外部事件 JSON 文件路径
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta


# ========== 数据源配置 ==========
# 方式1: 环境变量指定 westock-data 脚本路径（推荐，WorkBuddy 用户使用）
# export WESTOCK_DATA_SCRIPT="/Applications/WorkBuddy.app/Contents/Resources/.../index.js"
# 方式2: 使用 yfinance 作为 fallback（无需 WorkBuddy，需安装 yfinance）
# pip install yfinance

def get_westock_script_path():
    """获取 westock-data 脚本路径，优先从环境变量读取"""
    env_path = os.environ.get('WESTOCK_DATA_SCRIPT')
    if env_path and os.path.exists(env_path):
        return env_path
    # 尝试默认安装路径（macOS）
    default_path = "/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/resources/builtin-skills/westock-data/scripts/index.js"
    if os.path.exists(default_path):
        return default_path
    return None


def get_node_path():
    """获取 node 路径"""
    env_node = os.environ.get('NODE_PATH')
    if env_node and os.path.exists(env_node):
        return env_node
    node = shutil.which('node')
    if node:
        return node
    # 尝试常见安装路径
    for path in ['/usr/local/bin/node', '/opt/homebrew/bin/node', '/usr/bin/node']:
        if os.path.exists(path):
            return path
    return None


def run_westock_kline(symbol, start, end):
    """调用 westock-data 脚本获取 K 线数据"""
    script_path = get_westock_script_path()
    node_path = get_node_path()
    
    if not script_path:
        return None
    if not node_path:
        print(f"[WARN] 未找到 node，请安装 Node.js 或设置 NODE_PATH 环境变量", file=sys.stderr)
        return None
    
    # 判断市场类型
    prefix = 'us' if not symbol.isdigit() else 'sh' if symbol.startswith('6') else 'sz'
    cmd = [node_path, script_path, "kline", f"{prefix}{symbol}", "--period", "day", "--start", start, "--end", end]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"[WARN] westock-data 获取 {symbol} 失败: {result.stderr}", file=sys.stderr)
            return None
        return result.stdout
    except Exception as e:
        print(f"[WARN] westock-data 异常: {e}", file=sys.stderr)
        return None


def run_yfinance_kline(symbol, start, end):
    """使用 yfinance 获取 K 线数据（fallback）"""
    try:
        import yfinance as yf
    except ImportError:
        print(f"[WARN] yfinance 未安装，请执行: pip install yfinance", file=sys.stderr)
        return None
    
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start, end=end)
        if hist.empty:
            return None
        
        data = []
        for idx, row in hist.iterrows():
            data.append({'date': idx.strftime('%Y-%m-%d'), 'close': float(row['Close'])})
        data.sort(key=lambda x: x['date'])
        return data
    except Exception as e:
        print(f"[WARN] yfinance 获取 {symbol} 失败: {e}", file=sys.stderr)
        return None


def fetch_kline(symbol, start, end):
    """统一获取 K 线数据，优先 westock-data，fallback yfinance"""
    # 优先尝试 westock-data
    westock_data = run_westock_kline(symbol, start, end)
    if westock_data:
        return parse_westock_kline(westock_data)
    
    # fallback yfinance
    print(f"[INFO] 尝试使用 yfinance 获取 {symbol} 数据...")
    yf_data = run_yfinance_kline(symbol, start, end)
    if yf_data:
        return yf_data
    
    print(f"[ERROR] 无法获取 {symbol} 数据。请检查:")
    print(f"  1. 已安装 WorkBuddy 并设置 WESTOCK_DATA_SCRIPT 环境变量")
    print(f"  2. 或安装 yfinance: pip install yfinance")
    return None


def parse_westock_kline(csv_text):
    """解析 westock-data 返回的 K 线 CSV 数据"""
    data = []
    lines = csv_text.strip().split('\n')
    if len(lines) < 3:
        return data
    
    # Skip header and separator lines
    for line in lines[2:]:
        parts = line.split('|')
        if len(parts) >= 4:
            try:
                date = parts[1].strip()
                close = float(parts[3].strip())
                data.append({'date': date, 'close': close})
            except (ValueError, IndexError):
                continue
    
    data.sort(key=lambda x: x['date'])
    return data


def calc_stats(vals):
  """计算稳健统计量"""
  if not vals:
      return {}
  s = sorted(vals)
  n = len(s)
  avg = sum(s) / n
  median = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
  q1_idx = int(n * 0.25)
  q3_idx = int(n * 0.75)
  q1 = s[q1_idx]
  q3 = s[q3_idx]
  p75 = s[int(n * 0.75)]
  p90 = s[int(n * 0.90)]
  p95 = s[int(n * 0.95)]
  min_v = s[0]
  max_v = s[-1]
  return {
      'avg': avg, 'median': median, 'q1': q1, 'q3': q3,
      'p75': p75, 'p90': p90, 'p95': p95, 'min': min_v, 'max': max_v, 'n': n
  }


def classify_cause(aapl_ret, qqq_ret):
  """根据苹果和QQQ的跌幅判断暴跌原因"""
  if qqq_ret is None:
      return '整体偏空+自身弱'
  if qqq_ret > -0.3:
      return '自身导致'
  elif qqq_ret < -1.5:
      return '整体下挫'
  else:
      return '整体偏空+自身弱'


def analyze_crashes(stock_data, benchmark_data, threshold, events_map=None):
  """核心分析逻辑"""
  if not stock_data or len(stock_data) < 2:
      return None
  
  # Build benchmark lookup by date
  benchmark_by_date = {d['date']: d['close'] for d in benchmark_data}
  
  # Calculate daily returns and find drops
  drops = []
  for i in range(1, len(stock_data)):
      prev = stock_data[i - 1]
      curr = stock_data[i]
      ret = (curr['close'] - prev['close']) / prev['close'] * 100
      
      if ret < -threshold:
          # Find benchmark return on same day
          b_close_prev = benchmark_by_date.get(prev['date'])
          b_close_curr = benchmark_by_date.get(curr['date'])
          b_ret = None
          if b_close_prev and b_close_curr and b_close_prev > 0:
              b_ret = (b_close_curr - b_close_prev) / b_close_prev * 100
          
          cause = classify_cause(ret, b_ret)
          event = events_map.get(curr['date'], '') if events_map else ''
          if not event:
              if cause == '自身导致':
                  event = '待补充：股票自身利空事件'
              elif cause == '整体下挫':
                  event = '市场整体下挫'
              else:
                  event = '大盘偏空+自身承压'
          
          # Calculate recovery days
          recovery_days = None
          for j in range(i + 1, len(stock_data)):
              if stock_data[j]['close'] > prev['close']:
                  recovery_days = j - i
                  break
          
          # Next 5 days data
          next_5_days = []
          for j in range(i + 1, min(i + 6, len(stock_data))):
              day_ret = (stock_data[j]['close'] - curr['close']) / curr['close'] * 100
              next_5_days.append({'date': stock_data[j]['date'], 'return': day_ret})
          
          # Next rally (>2% gain)
          next_rally = None
          for j in range(i + 1, len(stock_data)):
              day_ret = (stock_data[j]['close'] - stock_data[j - 1]['close']) / stock_data[j - 1]['close'] * 100
              if day_ret > 2:
                  next_rally = {'date': stock_data[j]['date'], 'return': day_ret}
                  break
          
          drops.append({
              'date': curr['date'],
              'aapl_return': ret,
              'qqq_return': b_ret,
              'cause': cause,
              'event': event,
              'recovery_days': recovery_days,
              'next_5_days': next_5_days,
              'next_rally': next_rally,
              'pre_close': prev['close'],
              'drop_close': curr['close']
          })
  
  return drops


def generate_html(drops, stock_symbol, benchmark_symbol, start_date, end_date, threshold):
  """生成交互式 HTML 报告"""
  if not drops:
      return "<html><body><h1>无数据</h1></body></html>"
  
  total = len(drops)
  self_c = len([d for d in drops if d['cause'] == '自身导致'])
  market_c = len([d for d in drops if d['cause'] == '整体下挫'])
  mixed_c = len([d for d in drops if d['cause'] == '整体偏空+自身弱'])
  
  recoveries = [d['recovery_days'] for d in drops if d['recovery_days'] is not None]
  unrecovered = len([d for d in drops if d['recovery_days'] is None])
  
  all_stats = calc_stats(recoveries)
  
  self_recoveries = [d['recovery_days'] for d in drops if d['cause'] == '自身导致' and d['recovery_days'] is not None]
  market_recoveries = [d['recovery_days'] for d in drops if d['cause'] == '整体下挫' and d['recovery_days'] is not None]
  mixed_recoveries = [d['recovery_days'] for d in drops if d['cause'] == '整体偏空+自身弱' and d['recovery_days'] is not None]
  
  self_stats = calc_stats(self_recoveries)
  market_stats = calc_stats(market_recoveries)
  mixed_stats = calc_stats(mixed_recoveries)
  
  # Recovery probability
  def prob_within(recoveries_list, days):
      if not recoveries_list:
          return 0
      return sum(1 for r in recoveries_list if r <= days) / len(recoveries_list) * 100
  
  def prob_all(data_list, days):
      if not data_list:
          return 0
      return sum(1 for d in data_list if d['recovery_days'] is not None and d['recovery_days'] <= days) / len(data_list) * 100
  
  prob_all_recovered = {
      '2d': prob_within(recoveries, 2),
      '3d': prob_within(recoveries, 3),
      '5d': prob_within(recoveries, 5),
      '7d': prob_within(recoveries, 7),
      '10d': prob_within(recoveries, 10),
      '30d': prob_within(recoveries, 30),
      '60d': prob_within(recoveries, 60),
  }
  
  prob_by_cause = {}
  for cause_name in ['整体下挫', '整体偏空+自身弱', '自身导致']:
      cause_all = [d for d in drops if d['cause'] == cause_name]
      prob_by_cause[cause_name] = {
          '2d': prob_all(cause_all, 2),
          '3d': prob_all(cause_all, 3),
          '5d': prob_all(cause_all, 5),
          '7d': prob_all(cause_all, 7),
          '10d': prob_all(cause_all, 10),
          '30d': prob_all(cause_all, 30),
          '60d': prob_all(cause_all, 60),
          'count': len(cause_all),
          'recovered': len([d for d in cause_all if d['recovery_days'] is not None]),
          'unrecovered': len([d for d in cause_all if d['recovery_days'] is None]),
      }
  
  # Recovery distribution
  rec_dist = {}
  for d in drops:
      rd = d['recovery_days']
      if rd is None:
          rec_dist['未修复'] = rec_dist.get('未修复', 0) + 1
      elif rd == 1:
          rec_dist['1天'] = rec_dist.get('1天', 0) + 1
      elif rd == 2:
          rec_dist['2天'] = rec_dist.get('2天', 0) + 1
      elif rd <= 5:
          rec_dist['3-5天'] = rec_dist.get('3-5天', 0) + 1
      elif rd <= 10:
          rec_dist['6-10天'] = rec_dist.get('6-10天', 0) + 1
      elif rd <= 30:
          rec_dist['11-30天'] = rec_dist.get('11-30天', 0) + 1
      else:
          rec_dist['30天以上'] = rec_dist.get('30天以上', 0) + 1
  
  # Drop tier analysis
  def tier_by_drop(d):
      ret = abs(d['aapl_return'])
      if ret >= 5:
          return '>5%'
      if ret >= 4:
          return '4-5%'
      if ret >= 3:
          return '3-4%'
      return '2-3%'
  
  tier_names = ['2-3%', '3-4%', '4-5%', '>5%']
  tier_stats = {}
  for tier in tier_names:
      tier_data = [d for d in drops if tier_by_drop(d) == tier]
      tier_recoveries = [d['recovery_days'] for d in tier_data if d['recovery_days'] is not None]
      tier_stats[tier] = {
          'count': len(tier_data),
          'recovered': len(tier_recoveries),
          'unrecovered': len(tier_data) - len(tier_recoveries),
          'stats': calc_stats(tier_recoveries),
          'prob_3d': prob_all(tier_data, 3),
          'prob_5d': prob_all(tier_data, 5),
          'prob_7d': prob_all(tier_data, 7),
          'prob_10d': prob_all(tier_data, 10),
          'prob_30d': prob_all(tier_data, 30),
      }
  
  # Monthly distribution
  month_dist = {}
  for d in drops:
      m = int(d['date'][5:7])
      month_dist[m] = month_dist.get(m, 0) + 1
  
  # 5-day cumulative
  five_day_cum = []
  for d in drops:
      days = d['next_5_days']
      if days:
          cum = sum(day['return'] for day in days)
          five_day_cum.append(cum)
  
  # Bounce magnitude
  bounce_mags = []
  for d in drops:
      if d['recovery_days'] and d['next_5_days']:
          rd = d['recovery_days']
          if rd <= len(d['next_5_days']):
              bounce_mags.append(d['next_5_days'][rd - 1]['return'])
  
  bounce_stats = calc_stats(bounce_mags) if bounce_mags else {}
  
  # V-shape recovery
  v_shape = [d for d in drops if d['recovery_days'] and d['recovery_days'] <= 5]
  v_shape_pct = len(v_shape) / total * 100 if total > 0 else 0
  
  # SVG Charts
  def svg_donut(w, h, data_dict, colors):
      cx, cy = w // 2, h // 2 - 20
      r = min(w, h) * 0.30
      total_v = sum(data_dict.values())
      items = list(data_dict.items())
      
      svg = f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
      svg += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#e8e8ed" stroke-width="40"/>\n'
      
      circumference = 2 * 3.14159 * r
      offset = 0
      for i, (label, val) in enumerate(items):
          pct = val / total_v
          dash = pct * circumference
          gap = circumference - dash
          svg += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{colors[i]}" stroke-width="40" stroke-dasharray="{dash} {gap}" stroke-dashoffset="{-offset}" stroke-linecap="butt"/>\n'
          offset += dash
      
      svg += f'<circle cx="{cx}" cy="{cy}" r="{r * 0.55}" fill="white"/>\n'
      svg += f'<text x="{cx}" y="{cy - 8}" text-anchor="middle" font-size="16" font-weight="bold" fill="#1d1d1f">{total_v}</text>\n'
      svg += f'<text x="{cx}" y="{cy + 12}" text-anchor="middle" font-size="12" fill="#86868b">总次数</text>\n'
      
      y_legend = h - 25
      x_positions = [30, 170, 330]
      for i, (label, val) in enumerate(items):
          x = x_positions[i]
          svg += f'<rect x="{x}" y="{y_legend - 8}" width="12" height="12" fill="{colors[i]}" rx="2"/>\n'
          svg += f'<text x="{x + 18}" y="{y_legend + 3}" font-size="12" fill="#1d1d1f">{label}: {val}</text>\n'
      
      svg += '</svg>'
      return svg
  
  cause_colors = ['#86868b', '#0071e3', '#ff9500']
  cause_svg = svg_donut(500, 300, {'整体下挫': market_c, '整体偏空+自身弱': mixed_c, '自身导致': self_c}, cause_colors)
  
  rec_labels = ['1天', '2天', '3-5天', '6-10天', '11-30天', '30天以上', '未修复']
  rec_values = [rec_dist.get(l, 0) for l in rec_labels]
  rec_bar_colors = ['#34c759', '#30d158', '#0071e3', '#5856d6', '#ff3b30', '#af52de', '#86868b']
  
  def svg_bar(w, h, labels, values, colors):
      margin_l = 40
      margin_b = 30
      margin_t = 20
      chart_w = w - margin_l - 20
      chart_h = h - margin_b - margin_t
      max_v = max(values) if max(values) > 0 else 1
      
      svg = f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
      for i in range(6):
          y = margin_t + chart_h * (5 - i) / 5
          v = max_v * i / 5
          svg += f'<line x1="{margin_l}" y1="{y}" x2="{w - 20}" y2="{y}" stroke="#e8e8ed" stroke-width="1"/>\n'
          svg += f'<text x="{margin_l - 5}" y="{y + 3}" text-anchor="end" font-size="9" fill="#86868b">{int(v)}</text>\n'
      
      n = len(labels)
      bar_w = chart_w / n * 0.6
      gap = chart_w / n * 0.4
      for i, (l, v) in enumerate(zip(labels, values)):
          x = margin_l + gap / 2 + i * (chart_w / n)
          bar_h = (v / max_v) * chart_h if max_v > 0 else 0
          y = margin_t + chart_h - bar_h
          svg += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" fill="{colors[i]}" rx="3"/>\n'
          svg += f'<text x="{x + bar_w / 2}" y="{y - 5}" text-anchor="middle" font-size="10" fill="#1d1d1f" font-weight="600">{v}</text>\n'
          svg += f'<text x="{x + bar_w / 2}" y="{h - 8}" text-anchor="middle" font-size="9" fill="#86868b">{l}</text>\n'
      
      svg += '</svg>'
      return svg
  
  rec_svg = svg_bar(400, 280, rec_labels, rec_values, rec_bar_colors)
  
  month_labels = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
  month_values = [month_dist.get(i + 1, 0) for i in range(12)]
  month_colors = ['#0071e3'] * 12
  month_svg = svg_bar(480, 220, month_labels, month_values, month_colors)
  
  tier_labels = ['2-3%', '3-4%', '4-5%', '>5%']
  tier_values = [tier_stats[t]['count'] for t in tier_labels]
  tier_colors = ['#34c759', '#0071e3', '#ff9500', '#ff3b30']
  tier_svg = svg_bar(400, 220, tier_labels, tier_values, tier_colors)
  
  # Generate HTML
  stock_name = stock_symbol
  
  html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{stock_name} 暴跌分析 ({start_date} ~ {end_date})</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: #f5f5f7; margin: 0; padding: 0; color: #1d1d1f; }}

.layout {{ display: flex; min-height: 100vh; }}

.sidebar {{
  position: fixed; left: 0; top: 0; bottom: 0; width: 200px; background: #1d1d1f; color: white; padding: 20px 0; overflow-y: auto; z-index: 100; box-shadow: 2px 0 8px rgba(0,0,0,0.15);
}}
.sidebar-title {{ font-size: 15px; font-weight: 600; padding: 0 20px 16px; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 12px; color: white; }}
.sidebar-nav {{ list-style: none; padding: 0; margin: 0; }}
.sidebar-nav li {{ margin: 0; }}
.sidebar-nav a {{ display: block; padding: 10px 20px; color: rgba(255,255,255,0.75); text-decoration: none; font-size: 13px; transition: all 0.2s; border-left: 3px solid transparent; }}
.sidebar-nav a:hover, .sidebar-nav a.active {{ color: white; background: rgba(255,255,255,0.08); border-left-color: #0071e3; }}
.sidebar-nav .section-header {{ padding: 8px 20px 4px; font-size: 11px; color: rgba(255,255,255,0.4); text-transform: uppercase; letter-spacing: 0.5px; }}

main {{ margin-left: 200px; padding: 40px 30px; flex: 1; display: flex; justify-content: center; }}
.main-content {{ width: 100%; max-width: 1200px; margin: 0 auto; }}

h1 {{ text-align: center; color: #1d1d1f; margin-bottom: 8px; font-size: 26px; font-weight: 700; letter-spacing: -0.5px; }}
.subtitle {{ text-align: center; color: #86868b; margin-bottom: 40px; font-size: 14px; }}

.stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 40px; }}
.stat-card {{ background: white; border-radius: 16px; padding: 24px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.04); border: 1px solid #e8e8ed; }}
.stat-value {{ font-size: 36px; font-weight: 700; color: #ff3b30; letter-spacing: -1px; }}
.stat-label {{ font-size: 13px; color: #86868b; margin-top: 6px; }}
.stat-blue .stat-value {{ color: #0071e3; }}
.stat-green .stat-value {{ color: #34c759; }}
.stat-orange .stat-value {{ color: #ff9500; }}
.stat-purple .stat-value {{ color: #af52de; }}

.chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 40px; }}
.chart-card {{ background: white; border-radius: 16px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.04); border: 1px solid #e8e8ed; }}
.chart-title {{ font-size: 15px; font-weight: 600; margin-bottom: 8px; color: #1d1d1f; }}
.chart-svg {{ width: 100%; height: 280px; display: flex; justify-content: center; align-items: center; }}
.chart-svg svg {{ max-width: 100%; height: auto; }}

.section-title {{ font-size: 18px; font-weight: 700; margin: 40px 0 16px 0; color: #1d1d1f; letter-spacing: -0.3px; }}
.section-title:first-of-type {{ margin-top: 0; }}

.insight-card {{ background: white; border-radius: 16px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.04); border: 1px solid #e8e8ed; margin-bottom: 40px; }}
.insight-title {{ font-size: 15px; font-weight: 600; margin-bottom: 12px; color: #1d1d1f; }}
.insight-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 12px; }}
.insight-item {{ text-align: center; padding: 16px; border-radius: 12px; background: #f5f5f7; }}
.insight-value {{ font-size: 28px; font-weight: 700; color: #0071e3; }}
.insight-label {{ font-size: 13px; color: #86868b; margin-top: 6px; }}
.insight-sub {{ font-size: 11px; color: #86868b; margin-top: 2px; }}

.prob-table {{ width: 100%; margin-top: 12px; border-collapse: collapse; font-size: 13px; }}
.prob-table th {{ background: #f5f5f7; padding: 10px 8px; text-align: center; font-weight: 600; border: 1px solid #e8e8ed; color: #1d1d1f; }}
.prob-table td {{ padding: 10px 8px; text-align: center; border: 1px solid #e8e8ed; }}
.prob-table .row-label {{ font-weight: 600; text-align: left; background: #fafafa; }}
.prob-table tr:nth-child(even) {{ background: #fafafa; }}
.prob-table tr:hover {{ background: #f0f0f0; }}

.cause-stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 40px; }}
.cause-stat-card {{ background: white; border-radius: 16px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.04); border: 1px solid #e8e8ed; text-align: center; }}
.cause-stat-title {{ font-size: 14px; font-weight: 600; margin-bottom: 10px; }}
.cause-stat-value {{ font-size: 32px; font-weight: 700; color: #ff3b30; letter-spacing: -1px; }}
.cause-stat-sub {{ font-size: 13px; color: #86868b; margin-top: 6px; }}
.cause-stat-detail {{ font-size: 12px; color: #86868b; margin-top: 8px; line-height: 1.6; }}
.cause-stat-detail .stat-row {{ display: flex; justify-content: space-between; align-items: center; margin-top: 4px; font-size: 12px; }}
.cause-stat-detail .stat-row-label {{ color: #86868b; }}
.cause-stat-detail .stat-row-value {{ color: #1d1d1f; font-weight: 600; }}

.table-card {{ background: white; border-radius: 16px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.04); border: 1px solid #e8e8ed; margin-bottom: 40px; overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ background: #f5f5f7; padding: 12px 10px; text-align: left; font-weight: 600; color: #1d1d1f; border-bottom: 2px solid #e8e8ed; white-space: nowrap; position: sticky; top: 0; cursor: pointer; user-select: none; }}
th:hover {{ background: #e8e8ed; }}
th .sort-indicator {{ font-size: 10px; color: #86868b; margin-left: 4px; }}
td {{ padding: 10px; border-bottom: 1px solid #e8e8ed; white-space: nowrap; }}
td.col-wrap {{ white-space: normal; }}
tr:hover {{ background: #fafafa; }}
.red {{ color: #ff3b30; font-weight: 600; }}
.green {{ color: #34c759; font-weight: 600; }}
.gray {{ color: #86868b; }}
.blue {{ color: #0071e3; font-weight: 600; }}
.tag {{ display: inline-block; padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: 500; }}
.tag-self {{ background: #fff4e6; color: #d46b08; }}
.tag-market {{ background: #f0f0f0; color: #434343; }}
.tag-mixed {{ background: #e6f7ff; color: #096dd9; }}

.filter-bar {{ display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; align-items: center; background: #f5f5f7; padding: 12px 14px; border-radius: 10px; }}
.filter-input {{ padding: 8px 14px; border: 1px solid #e8e8ed; border-radius: 8px; font-size: 13px; width: 240px; outline: none; background: white; transition: border-color 0.2s; }}
.filter-input:focus {{ border-color: #0071e3; }}
.filter-select {{ padding: 8px 12px; border: 1px solid #e8e8ed; border-radius: 8px; font-size: 13px; outline: none; background: white; }}
.filter-count {{ font-size: 12px; color: #86868b; margin-left: auto; font-weight: 500; }}
.no-match {{ text-align: center; padding: 30px; color: #86868b; font-size: 14px; display: none; }}
.filter-clear {{ padding: 8px 16px; border: 1px solid #e8e8ed; border-radius: 8px; font-size: 12px; background: white; cursor: pointer; color: #434343; transition: all 0.2s; }}
.filter-clear:hover {{ background: #f5f5f7; border-color: #0071e3; }}

.filter-cb-group {{ display: flex; gap: 8px; align-items: center; }}
.filter-cb-label {{ display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 13px; padding: 4px 8px; border-radius: 6px; transition: background 0.15s; }}
.filter-cb-label:hover {{ background: rgba(0,0,0,0.04); }}
.filter-cb {{ width: 14px; height: 14px; cursor: pointer; accent-color: #0071e3; }}
.filter-cb-label .tag {{ font-size: 10px; padding: 2px 6px; }}

.note {{ font-size: 12px; color: #86868b; margin-top: 10px; line-height: 1.6; }}
.note strong {{ color: #1d1d1f; }}

.tier-table {{ width: 100%; margin-top: 12px; border-collapse: collapse; font-size: 13px; }}
.tier-table th {{ background: #f5f5f7; padding: 10px 8px; text-align: center; font-weight: 600; border: 1px solid #e8e8ed; }}
.tier-table td {{ padding: 10px 8px; text-align: center; border: 1px solid #e8e8ed; }}
.tier-table .row-label {{ font-weight: 600; text-align: left; background: #fafafa; }}
.tier-table tr:nth-child(even) {{ background: #fafafa; }}
.tier-table tr:hover {{ background: #f0f0f0; }}

@media (max-width: 1200px) {{
  .chart-row {{ grid-template-columns: 1fr; }}
  .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .cause-stats {{ grid-template-columns: repeat(2, 1fr); }}
  .insight-grid {{ grid-template-columns: repeat(2, 1fr); }}
}}
@media (max-width: 768px) {{
  .sidebar {{ width: 160px; }}
  main {{ margin-left: 160px; padding: 20px 15px; }}
  .stats-grid {{ grid-template-columns: 1fr 1fr; }}
  .insight-grid {{ grid-template-columns: 1fr 1fr; }}
  .filter-cb-group {{ flex-wrap: wrap; }}
}}
</style>
</head>
<body>
<div class="layout">
<aside class="sidebar">
  <div class="sidebar-title">{stock_name} 暴跌分析</div>
  <ul class="sidebar-nav">
    <li><a href="#overview" class="active">概览</a></li>
    <li class="section-header">统计</li>
    <li><a href="#recovery-prob">修复概率</a></li>
    <li><a href="#cause-stats">原因分类</a></li>
    <li><a href="#drop-tier">跌幅分层</a></li>
    <li><a href="#month-dist">月度分布</a></li>
    <li class="section-header">表格</li>
    <li><a href="#main-table">暴跌事件列表</a></li>
    <li><a href="#after5-table">大跌后5天</a></li>
    <li><a href="#rally-table">大跌后大涨</a></li>
  </ul>
</aside>

<main>
<div class="main-content">
  <h1>{stock_name} 暴跌分析</h1>
  <div class="subtitle">{start_date} ~ {end_date} | 日跌幅 > {threshold}% 的全部交易日</div>

  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-value">{total}</div>
      <div class="stat-label">暴跌次数 (&gt;{threshold}%)</div>
    </div>
    <div class="stat-card stat-blue">
      <div class="stat-value">{all_stats.get('median', 0):.0f}</div>
      <div class="stat-label">中位数修复天数</div>
    </div>
    <div class="stat-card stat-green">
      <div class="stat-value">{v_shape_pct:.0f}%</div>
      <div class="stat-label">5天内V型修复率</div>
    </div>
    <div class="stat-card stat-orange">
      <div class="stat-value">{self_c}</div>
      <div class="stat-label">自身因素导致</div>
    </div>
  </div>

  <div id="overview" class="chart-row">
    <div class="chart-card">
      <div class="chart-title">暴跌原因分布</div>
      <div class="chart-svg">{cause_svg}</div>
    </div>
    <div class="chart-card">
      <div class="chart-title">修复天数分布</div>
      <div class="chart-svg">{rec_svg}</div>
    </div>
  </div>
'''

  # Recovery Probability Section
  html += '''
  <div class="section-title" id="recovery-prob">修复概率统计</div>
  <div class="insight-card">
    <div class="insight-title">暴跌后 N 天内修复概率 <span style="font-size:11px;color:#86868b;font-weight:400;">（修复 = 收盘价超过暴跌前一日）</span></div>
    <div class="insight-grid">
'''

  for days, label in [(2, '2天内'), (3, '3天内'), (5, '5天内'), (7, '7天内'), (30, '30天内'), (60, '60天内')]:
      prob = prob_all_recovered[f'{days}d']
      html += f'''
      <div class="insight-item">
        <div class="insight-value">{prob:.1f}%</div>
        <div class="insight-label">{label}</div>
        <div class="insight-sub">{int(prob / 100 * len(recoveries))}/{len(recoveries)} 次</div>
      </div>
'''

  html += f'''      </div>
    <p style="font-size:12px;color:#86868b;margin-top:12px;text-align:center;">基于已修复的 {len(recoveries)} 次暴跌计算</p>
  </div>
'''

  # Cause-based recovery prob table
  html += '''
  <div class="insight-card">
    <div class="insight-title">按原因分类修复概率 <span style="font-size:11px;color:#86868b;font-weight:400;">（包含未修复事件，分母为总次数）</span></div>
    <table class="prob-table">
      <thead>
        <tr>
          <th>原因</th>
          <th>总次数</th>
          <th>未修复</th>
          <th>2天内</th>
          <th>3天内</th>
          <th>5天内</th>
          <th>7天内</th>
          <th>10天内</th>
          <th>30天内</th>
          <th>60天内</th>
        </tr>
      </thead>
      <tbody>
'''

  for cause_name, cause_label in [('整体下挫', '整体下挫'), ('整体偏空+自身弱', '整体偏空+自身弱'), ('自身导致', '自身导致')]:
      p = prob_by_cause[cause_name]
      tag_class = 'tag-market' if cause_name == '整体下挫' else ('tag-mixed' if cause_name == '整体偏空+自身弱' else 'tag-self')
      html += f'''          <tr>
          <td class="row-label"><span class="tag {tag_class}">{cause_label}</span></td>
          <td>{p['count']}</td>
          <td>{p['unrecovered']}</td>
          <td>{p['2d']:.1f}%</td>
          <td>{p['3d']:.1f}%</td>
          <td>{p['5d']:.1f}%</td>
          <td>{p['7d']:.1f}%</td>
          <td>{p['10d']:.1f}%</td>
          <td>{p['30d']:.1f}%</td>
          <td>{p['60d']:.1f}%</td>
        </tr>
'''

  html += '''        </tbody>
    </table>
  </div>
'''

  # Cause-based stats
  html += '''
  <div class="section-title" id="cause-stats">按原因分类修复统计</div>
  <div class="cause-stats">
'''

  cause_stats_data = [
      ('整体下挫', market_stats, market_c, 'tag-market'),
      ('整体偏空+自身弱', mixed_stats, mixed_c, 'tag-mixed'),
      ('自身导致', self_stats, self_c, 'tag-self'),
  ]

  for cause_name, stats, count, tag_class in cause_stats_data:
      if stats:
          html += f'''      <div class="cause-stat-card">
      <div class="cause-stat-title"><span class="tag {tag_class}">{cause_name}</span></div>
      <div class="cause-stat-value">{stats['median']:.0f}</div>
      <div class="cause-stat-sub">中位数修复天数</div>
      <div class="cause-stat-detail">
        <div class="stat-row"><span class="stat-row-label">平均值</span><span class="stat-row-value">{stats['avg']:.1f}天</span></div>
        <div class="stat-row"><span class="stat-row-label">25%分位数（较快修复）</span><span class="stat-row-value">{stats['q1']:.0f}天</span></div>
        <div class="stat-row"><span class="stat-row-label">75%分位数（较慢修复）</span><span class="stat-row-value">{stats['q3']:.0f}天</span></div>
        <div class="stat-row"><span class="stat-row-label">75%事件在几天内修复</span><span class="stat-row-value">{stats['p75']:.0f}天</span></div>
        <div class="stat-row"><span class="stat-row-label">90%事件在几天内修复</span><span class="stat-row-value">{stats['p90']:.0f}天</span></div>
        <div class="stat-row"><span class="stat-row-label">最快 ~ 最慢</span><span class="stat-row-value">{stats['min']:.0f} ~ {stats['max']:.0f}天</span></div>
      </div>
      <div class="cause-stat-sub">{count}次 ({stats['n']}次已修复)</div>
    </div>
'''
      else:
          html += f'''      <div class="cause-stat-card">
      <div class="cause-stat-title"><span class="tag {tag_class}">{cause_name}</span></div>
      <div class="cause-stat-value">—</div>
      <div class="cause-stat-sub">无修复数据</div>
    </div>
'''

  html += '''    </div>
'''

  # Drop tier analysis
  html += '''
  <div class="section-title" id="drop-tier">按跌幅分层修复统计</div>
  <div class="insight-card">
    <div class="insight-title">跌幅越大的暴跌，修复越慢、越困难</div>
    <table class="tier-table">
      <thead>
        <tr>
          <th>跌幅区间</th>
          <th>次数</th>
          <th>未修复</th>
          <th>3天内</th>
          <th>5天内</th>
          <th>7天内</th>
          <th>10天内</th>
          <th>30天内</th>
          <th>中位数修复</th>
          <th>75%分位</th>
          <th>90%分位</th>
        </tr>
      </thead>
      <tbody>
'''

  for tier in tier_names:
      ts = tier_stats[tier]
      s = ts['stats']
      html += f'''          <tr>
          <td class="row-label">{tier}</td>
          <td>{ts['count']}</td>
          <td>{ts['unrecovered']}</td>
          <td>{ts['prob_3d']:.1f}%</td>
          <td>{ts['prob_5d']:.1f}%</td>
          <td>{ts['prob_7d']:.1f}%</td>
          <td>{ts['prob_10d']:.1f}%</td>
          <td>{ts['prob_30d']:.1f}%</td>
          <td>{s['median']:.0f}天</td>
          <td>{s['q3']:.0f}天</td>
          <td>{s['p90']:.0f}天</td>
        </tr>
'''

  html += '''        </tbody>
    </table>
  </div>
'''

  # Monthly distribution
  html += '''
  <div class="section-title" id="month-dist">暴跌月度分布</div>
  <div class="chart-row">
    <div class="chart-card">
      <div class="chart-title">各月暴跌次数</div>
      <div class="chart-svg">''' + month_svg + '''</div>
    </div>
    <div class="chart-card">
      <div class="chart-title">各跌幅区间分布</div>
      <div class="chart-svg">''' + tier_svg + '''</div>
    </div>
  </div>
'''

  # Investment insights
  avg_5d = sum(five_day_cum) / len(five_day_cum) if five_day_cum else 0
  red_prob_5d = sum(1 for c in five_day_cum if c > 0) / len(five_day_cum) * 100 if five_day_cum else 0
  
  html += f'''
  <div class="section-title" id="insights">投资关键洞察</div>
  <div class="insight-card">
    <div class="insight-title">对交易决策有意义的统计</div>
    <div class="insight-grid" style="grid-template-columns: repeat(2, 1fr);">
      <div class="insight-item" style="text-align:left;">
        <div style="font-size:13px;font-weight:600;color:#1d1d1f;margin-bottom:6px;">暴跌后5天平均收益</div>
        <div style="font-size:28px;font-weight:700;color:#0071e3;">{avg_5d:.2f}%</div>
        <div style="font-size:11px;color:#86868b;margin-top:4px;">{total}次暴跌后5天累计收益平均值</div>
      </div>
      <div class="insight-item" style="text-align:left;">
        <div style="font-size:13px;font-weight:600;color:#1d1d1f;margin-bottom:6px;">5天内收红概率</div>
        <div style="font-size:28px;font-weight:700;color:#34c759;">{red_prob_5d:.1f}%</div>
        <div style="font-size:11px;color:#86868b;margin-top:4px;">暴跌后5天累计为正的比例</div>
      </div>
      <div class="insight-item" style="text-align:left;">
        <div style="font-size:13px;font-weight:600;color:#1d1d1f;margin-bottom:6px;">修复日平均反弹幅度</div>
        <div style="font-size:28px;font-weight:700;color:#0071e3;">+{bounce_stats.get('avg', 0):.2f}%</div>
        <div style="font-size:11px;color:#86868b;margin-top:4px;">修复当天（收盘价超过前跌日）的平均涨幅</div>
      </div>
      <div class="insight-item" style="text-align:left;">
        <div style="font-size:13px;font-weight:600;color:#1d1d1f;margin-bottom:6px;">自身原因 vs 市场原因 修复慢多少</div>
        <div style="font-size:28px;font-weight:700;color:#ff9500;">{self_stats.get('median', 0) - market_stats.get('median', 0):.0f}天</div>
        <div style="font-size:11px;color:#86868b;margin-top:4px;">自身原因修复中位数 - 市场整体下挫修复中位数</div>
      </div>
    </div>
  </div>
'''

  # Main table
  html += f'''
  <div class="section-title" id="main-table">一、全部暴跌事件列表</div>
  <div class="table-card">
    <div class="filter-bar">
      <input type="text" class="filter-input" id="mainFilter" placeholder="搜索关键词：日期、事件、原因..." oninput="filterTable('mainTable', 'mainFilter', 'mainFilterCause', 'mainFilterYear')">
      <div class="filter-cb-group" id="mainFilterCause" onchange="filterTable('mainTable', 'mainFilter', 'mainFilterCause', 'mainFilterYear')">
        <label class="filter-cb-label"><input type="checkbox" class="filter-cb" value="整体下挫" checked><span class="tag tag-market">整体下挫</span></label>
        <label class="filter-cb-label"><input type="checkbox" class="filter-cb" value="整体偏空+自身弱" checked><span class="tag tag-mixed">整体偏空+自身弱</span></label>
        <label class="filter-cb-label"><input type="checkbox" class="filter-cb" value="自身导致" checked><span class="tag tag-self">自身导致</span></label>
      </div>
      <select class="filter-select" id="mainFilterYear" onchange="filterTable('mainTable', 'mainFilter', 'mainFilterCause', 'mainFilterYear')">
        <option value="">全部年份</option>
'''
  
  years = sorted(set(d['date'][:4] for d in drops))
  for y in years:
      html += f'          <option value="{y}">{y}</option>\n'
  
  html += f'''        </select>
      <button class="filter-clear" onclick="clearFilters('mainTable', ['mainFilter','mainFilterCause','mainFilterYear'])">清除筛选</button>
      <span class="filter-count" id="mainCount">共 {total} 条</span>
    </div>
    <div class="no-match" id="mainNoMatch">未找到匹配数据</div>
    <table id="mainTable" data-sort-dir="">
      <thead>
        <tr>
          <th onclick="sortTable('mainTable', 0, 'date')">日期 <span class="sort-indicator" id="mainSort0">↕</span></th>
          <th onclick="sortTable('mainTable', 1, 'number')">{stock_name}跌幅 <span class="sort-indicator" id="mainSort1">↕</span></th>
          <th>{benchmark_symbol}涨跌</th>
          <th>原因</th>
          <th onclick="sortTable('mainTable', 4, 'number')">修复天数 <span class="sort-indicator" id="mainSort4">↕</span></th>
          <th>事件/背景</th>
          <th>大跌后首次大涨</th>
        </tr>
      </thead>
      <tbody>
'''

  for d in reversed(drops):
      aapl_ret = d['aapl_return']
      qqq_ret = d['qqq_return']
      rd = d['recovery_days']
      rd_str = f'{rd}天' if rd else '未修复'
      cause_class = 'tag-self' if d['cause'] == '自身导致' else ('tag-market' if d['cause'] == '整体下挫' else 'tag-mixed')
      rally = d['next_rally']
      if rally:
          rally_str = f"{rally['date']} <span class='green'>(+{rally['return']:.2f}%)</span>"
      else:
          rally_str = '暂无'
      qqq_str = f"{qqq_ret:.2f}%" if qqq_ret is not None else 'N/A'
      qqq_color = 'green' if qqq_ret and qqq_ret > 0 else 'red' if qqq_ret and qqq_ret < 0 else 'gray'
      
      html += f'''          <tr data-cause="{d['cause']}" data-year="{d['date'][:4]}">
          <td>{d['date']}</td>
          <td class="red">{aapl_ret:.2f}%</td>
          <td class="{qqq_color}">{qqq_str}</td>
          <td><span class="tag {cause_class}">{d['cause']}</span></td>
          <td>{rd_str}</td>
          <td class="col-wrap">{d['event']}</td>
          <td>{rally_str}</td>
        </tr>
'''

  html += '''        </tbody>
    </table>
  </div>
'''

  # After 5 days table
  html += f'''
  <div class="section-title" id="after5-table">二、大跌后最近五天涨跌情况</div>
  <div class="table-card">
    <div class="filter-bar">
      <input type="text" class="filter-input" id="after5Filter" placeholder="搜索关键词：日期、事件、原因..." oninput="filterTable('after5Table', 'after5Filter', 'after5FilterCause', 'after5FilterYear')">
      <div class="filter-cb-group" id="after5FilterCause" onchange="filterTable('after5Table', 'after5Filter', 'after5FilterCause', 'after5FilterYear')">
        <label class="filter-cb-label"><input type="checkbox" class="filter-cb" value="整体下挫" checked><span class="tag tag-market">整体下挫</span></label>
        <label class="filter-cb-label"><input type="checkbox" class="filter-cb" value="整体偏空+自身弱" checked><span class="tag tag-mixed">整体偏空+自身弱</span></label>
        <label class="filter-cb-label"><input type="checkbox" class="filter-cb" value="自身导致" checked><span class="tag tag-self">自身导致</span></label>
      </div>
      <select class="filter-select" id="after5FilterYear" onchange="filterTable('after5Table', 'after5Filter', 'after5FilterCause', 'after5FilterYear')">
        <option value="">全部年份</option>
'''
  for y in years:
      html += f'          <option value="{y}">{y}</option>\n'
  
  html += f'''        </select>
      <button class="filter-clear" onclick="clearFilters('after5Table', ['after5Filter','after5FilterCause','after5FilterYear'])">清除筛选</button>
      <span class="filter-count" id="after5Count">共 {total} 条</span>
    </div>
    <div class="no-match" id="after5NoMatch">未找到匹配数据</div>
    <table id="after5Table" data-sort-dir="">
      <thead>
        <tr>
          <th onclick="sortTable('after5Table', 0, 'date')">暴跌日期 <span class="sort-indicator" id="after5Sort0">↕</span></th>
          <th onclick="sortTable('after5Table', 1, 'number')">{stock_name}跌幅 <span class="sort-indicator" id="after5Sort1">↕</span></th>
          <th>原因</th>
          <th>第1天</th>
          <th>第2天</th>
          <th>第3天</th>
          <th>第4天</th>
          <th>第5天</th>
          <th>5天累计</th>
        </tr>
      </thead>
      <tbody>
'''

  for d in reversed(drops):
      aapl_ret = d['aapl_return']
      cause_class = 'tag-self' if d['cause'] == '自身导致' else ('tag-market' if d['cause'] == '整体下挫' else 'tag-mixed')
      
      days = d['next_5_days']
      day_cells = []
      total_5 = 0
      for i in range(5):
          if i < len(days):
              ret = days[i]['return']
              total_5 += ret
              color = 'green' if ret > 0 else 'red' if ret < 0 else 'gray'
              day_cells.append(f'<td class="{color}">{ret:.2f}%</td>')
          else:
              day_cells.append('<td class="gray">—</td>')
      
      total_color = 'green' if total_5 > 0 else 'red' if total_5 < 0 else 'gray'
      
      html += f'''          <tr data-cause="{d['cause']}" data-year="{d['date'][:4]}">
          <td>{d['date']}</td>
          <td class="red">{aapl_ret:.2f}%</td>
          <td><span class="tag {cause_class}">{d['cause']}</span></td>
          {''.join(day_cells)}
          <td class="{total_color}">{total_5:.2f}%</td>
        </tr>
'''

  html += '''        </tbody>
    </table>
  </div>
'''

  # Rally table
  html += f'''
  <div class="section-title" id="rally-table">三、大跌后最近一次大涨</div>
  <div class="table-card">
    <div class="filter-bar">
      <input type="text" class="filter-input" id="rallyFilter" placeholder="搜索关键词：日期、事件、原因..." oninput="filterTable('rallyTable', 'rallyFilter', 'rallyFilterCause', 'rallyFilterYear')">
      <div class="filter-cb-group" id="rallyFilterCause" onchange="filterTable('rallyTable', 'rallyFilter', 'rallyFilterCause', 'rallyFilterYear')">
        <label class="filter-cb-label"><input type="checkbox" class="filter-cb" value="整体下挫" checked><span class="tag tag-market">整体下挫</span></label>
        <label class="filter-cb-label"><input type="checkbox" class="filter-cb" value="整体偏空+自身弱" checked><span class="tag tag-mixed">整体偏空+自身弱</span></label>
        <label class="filter-cb-label"><input type="checkbox" class="filter-cb" value="自身导致" checked><span class="tag tag-self">自身导致</span></label>
      </div>
      <select class="filter-select" id="rallyFilterYear" onchange="filterTable('rallyTable', 'rallyFilter', 'rallyFilterCause', 'rallyFilterYear')">
        <option value="">全部年份</option>
'''
  for y in years:
      html += f'          <option value="{y}">{y}</option>\n'
  
  html += f'''        </select>
      <button class="filter-clear" onclick="clearFilters('rallyTable', ['rallyFilter','rallyFilterCause','rallyFilterYear'])">清除筛选</button>
      <span class="filter-count" id="rallyCount">共 {total} 条</span>
    </div>
    <div class="no-match" id="rallyNoMatch">未找到匹配数据</div>
    <table id="rallyTable" data-sort-dir="">
      <thead>
        <tr>
          <th onclick="sortTable('rallyTable', 0, 'date')">暴跌日期 <span class="sort-indicator" id="rallySort0">↕</span></th>
          <th onclick="sortTable('rallyTable', 1, 'number')">{stock_name}跌幅 <span class="sort-indicator" id="rallySort1">↕</span></th>
          <th>{benchmark_symbol}涨跌</th>
          <th>原因</th>
          <th onclick="sortTable('rallyTable', 4, 'date')">首次大涨日期 <span class="sort-indicator" id="rallySort4">↕</span></th>
          <th onclick="sortTable('rallyTable', 5, 'number')">大涨幅度 <span class="sort-indicator" id="rallySort5">↕</span></th>
          <th onclick="sortTable('rallyTable', 6, 'number')">间隔天数 <span class="sort-indicator" id="rallySort6">↕</span></th>
          <th>事件</th>
        </tr>
      </thead>
      <tbody>
'''

  for d in reversed(drops):
      aapl_ret = d['aapl_return']
      qqq_ret = d['qqq_return']
      rally = d['next_rally']
      cause_class = 'tag-self' if d['cause'] == '自身导致' else ('tag-market' if d['cause'] == '整体下挫' else 'tag-mixed')
      
      if rally:
          rally_date = datetime.strptime(rally['date'], '%Y-%m-%d')
          drop_date = datetime.strptime(d['date'], '%Y-%m-%d')
          gap = (rally_date - drop_date).days
          qqq_str = f'{qqq_ret:.2f}%' if qqq_ret is not None else 'N/A'
          html += f'''          <tr data-cause="{d['cause']}" data-year="{d['date'][:4]}">
          <td>{d['date']}</td>
          <td class="red">{aapl_ret:.2f}%</td>
          <td>{qqq_str}</td>
          <td><span class="tag {cause_class}">{d['cause']}</span></td>
          <td>{rally['date']}</td>
          <td class="green">+{rally['return']:.2f}%</td>
          <td>{gap}天</td>
          <td class="col-wrap">{d['event']}</td>
        </tr>
'''
      else:
          qqq_str = f'{qqq_ret:.2f}%' if qqq_ret is not None else 'N/A'
          html += f'''          <tr data-cause="{d['cause']}" data-year="{d['date'][:4]}">
          <td>{d['date']}</td>
          <td class="red">{aapl_ret:.2f}%</td>
          <td>{qqq_str}</td>
          <td><span class="tag {cause_class}">{d['cause']}</span></td>
          <td class="gray">—</td>
          <td class="gray">—</td>
          <td class="gray">—</td>
          <td class="col-wrap">{d['event']}</td>
        </tr>
'''

  html += '''        </tbody>
    </table>
  </div>

  <div class="note">
    <p><strong>数据说明：</strong></p>
    <p>1. 数据范围：{start_date} 至 {end_date}，筛选日跌幅 > {threshold}% 共 {total} 次。</p>
    <p>2. <strong>修复天数</strong>：收盘价重新超过暴跌前一日收盘价所需交易日数。</p>
    <p>3. <strong>25%分位数</strong>：25%的事件在这个天数内修复（较快修复）。<strong>75%分位数</strong>：75%的事件在这个天数内修复（较慢修复）。<strong>90%分位数</strong>：90%的事件在这个天数内修复。</p>
    <p>4. 原因判定：<strong>自身导致</strong>（{benchmark_symbol}涨或微跌，{stock_name}独跌）、<strong>整体下挫</strong>（{benchmark_symbol}跌幅 > 1.5%，大盘同步跌）、<strong>整体偏空+自身弱</strong>（{benchmark_symbol}跌0.5%~1.5%，{stock_name}跌更多）。</p>
    <p>5. <strong>V型修复</strong>：暴跌后5个交易日内收盘价回到暴跌前水平。</p>
    <p>6. 数据来源：腾讯自选股。事件信息基于公开资料整理。本报告仅供分析参考，不构成投资建议。</p>
  </div>
</div>
</main>
</div>

<script>
function getCheckedCauses(causeGroupId) {
const group = document.getElementById(causeGroupId);
if (!group) return [];
return Array.from(group.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value);
}

function filterTable(tableId, textFilterId, causeGroupId, yearFilterId) {
const table = document.getElementById(tableId);
const textFilter = document.getElementById(textFilterId).value.toLowerCase().trim();
const checkedCauses = getCheckedCauses(causeGroupId);
const yearFilter = document.getElementById(yearFilterId).value;
const rows = table.querySelectorAll('tbody tr');
const noMatchDiv = document.getElementById(tableId.replace('Table', 'NoMatch'));
const countSpan = document.getElementById(tableId.replace('Table', 'Count'));

let visibleCount = 0;

rows.forEach(row => {
  const text = row.textContent.toLowerCase();
  const cause = row.getAttribute('data-cause');
  const year = row.getAttribute('data-year');
  
  let matchText = true;
  let matchCause = true;
  let matchYear = true;
  
  if (textFilter) {
    matchText = text.includes(textFilter);
  }
  if (checkedCauses.length > 0) {
    matchCause = checkedCauses.includes(cause);
  }
  if (yearFilter) {
    matchYear = year === yearFilter;
  }
  
  if (matchText && matchCause && matchYear) {
    row.style.display = '';
    visibleCount++;
  } else {
    row.style.display = 'none';
  }
});

if (noMatchDiv) {
  noMatchDiv.style.display = visibleCount === 0 ? 'block' : 'none';
}

if (countSpan) {
  countSpan.textContent = '共 ' + visibleCount + ' 条';
}
}

function clearFilters(tableId, filterIds) {
filterIds.forEach(id => {
  const el = document.getElementById(id);
  if (!el) return;
  if (el.tagName === 'SELECT' || el.tagName === 'INPUT') {
    if (el.type === 'checkbox') {
      el.checked = true;
    } else {
      el.value = '';
    }
  } else if (el.classList.contains('filter-cb-group')) {
    el.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
  }
});
const textFilterId = filterIds[0];
filterTable(tableId, textFilterId, filterIds[1], filterIds[2]);
}

function sortTable(tableId, colIndex, type) {
const table = document.getElementById(tableId);
const tbody = table.querySelector('tbody');
const rows = Array.from(tbody.querySelectorAll('tr'));

let dir = table.getAttribute('data-sort-dir') || 'asc';
if (table.getAttribute('data-sort-col') === String(colIndex)) {
  dir = dir === 'asc' ? 'desc' : 'asc';
} else {
  dir = 'asc';
}
table.setAttribute('data-sort-dir', dir);
table.setAttribute('data-sort-col', colIndex);

table.querySelectorAll('.sort-indicator').forEach(el => el.textContent = '↕');
const indicator = document.getElementById(tableId.replace('Table', 'Sort') + colIndex);
if (indicator) indicator.textContent = dir === 'asc' ? '↑' : '↓';

rows.sort((a, b) => {
  const aText = a.cells[colIndex].textContent.trim();
  const bText = b.cells[colIndex].textContent.trim();
  
  let aVal, bVal;
  if (type === 'number') {
    aVal = parseFloat(aText.replace(/[+%天,暂无]/g, ''));
    bVal = parseFloat(bText.replace(/[+%天,暂无]/g, ''));
    if (isNaN(aVal)) aVal = -Infinity;
    if (isNaN(bVal)) bVal = -Infinity;
  } else if (type === 'date') {
    if (aText === '—' || aText === '暂无') aVal = new Date('9999-12-31');
    else aVal = new Date(aText);
    if (bText === '—' || bText === '暂无') bVal = new Date('9999-12-31');
    else bVal = new Date(bText);
  } else {
    aVal = aText;
    bVal = bText;
  }
  
  if (aVal < bVal) return dir === 'asc' ? -1 : 1;
  if (aVal > bVal) return dir === 'asc' ? 1 : -1;
  return 0;
});

rows.forEach(row => tbody.appendChild(row));
}

const sections = document.querySelectorAll('.section-title, #overview');
const navLinks = document.querySelectorAll('.sidebar-nav a');

function updateActive() {
let current = '';
sections.forEach(section => {
  const sectionTop = section.offsetTop;
  if (window.scrollY + 100 >= sectionTop) {
    current = section.getAttribute('id');
  }
});

navLinks.forEach(link => {
  link.classList.remove('active');
  if (link.getAttribute('href') === '#' + current) {
    link.classList.add('active');
  }
});
}

window.addEventListener('scroll', updateActive);

document.querySelectorAll('.sidebar-nav a').forEach(anchor => {
anchor.addEventListener('click', function(e) {
  e.preventDefault();
  const target = document.querySelector(this.getAttribute('href'));
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
});
});
</script>
</body>
</html>
'''
  
  return html


def main():
  parser = argparse.ArgumentParser(description='Stock Crash Analyzer - 股票暴跌分析器')
  parser.add_argument('--stock', required=True, help='目标股票代码（如 AAPL）')
  parser.add_argument('--benchmark', default='QQQ', help='对比指数（默认 QQQ）')
  parser.add_argument('--start', required=True, help='开始日期（YYYY-MM-DD）')
  parser.add_argument('--end', required=True, help='结束日期（YYYY-MM-DD）')
  parser.add_argument('--threshold', type=float, default=2.0, help='暴跌阈值（百分比，默认 2.0）')
  parser.add_argument('--output', required=True, help='输出 HTML 文件路径')
  parser.add_argument('--events', help='可选：外部事件 JSON 文件路径')
  
  args = parser.parse_args()
  
  print(f"正在获取 {args.stock} 数据...")
  stock_data = fetch_kline(args.stock, args.start, args.end)
  if not stock_data:
      print(f"获取 {args.stock} 数据失败")
      sys.exit(1)
  
  print(f"正在获取 {args.benchmark} 数据...")
  benchmark_data = fetch_kline(args.benchmark, args.start, args.end)
  if not benchmark_data:
      print(f"获取 {args.benchmark} 数据失败")
      sys.exit(1)
  
  print(f"{args.stock}: {len(stock_data)} 个交易日")
  print(f"{args.benchmark}: {len(benchmark_data)} 个交易日")
  
  # Load events if provided
  events_map = None
  if args.events and os.path.exists(args.events):
      with open(args.events) as f:
          events_map = json.load(f)
  
  print(f"分析暴跌事件（阈值 > {args.threshold}%）...")
  drops = analyze_crashes(stock_data, benchmark_data, args.threshold, events_map)
  
  if not drops:
      print(f"未找到日跌幅 > {args.threshold}% 的交易日")
      sys.exit(0)
  
  print(f"发现 {len(drops)} 次暴跌")
  
  print("生成 HTML 报告...")
  html = generate_html(drops, args.stock, args.benchmark, args.start, args.end, args.threshold)
  
  with open(args.output, 'w') as f:
      f.write(html)
  
  print(f"报告已保存: {args.output}")
  print(f"  - 暴跌次数: {len(drops)}")
  print(f"  - 自身导致: {len([d for d in drops if d['cause'] == '自身导致'])}")
  print(f"  - 整体下挫: {len([d for d in drops if d['cause'] == '整体下挫'])}")
  print(f"  - 整体偏空+自身弱: {len([d for d in drops if d['cause'] == '整体偏空+自身弱'])}")


if __name__ == '__main__':
  main()
