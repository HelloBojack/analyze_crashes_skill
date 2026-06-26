# stock-crash-analyzer

[English](./README_EN.md) | 中文

股票暴跌智能分析工具。输入任意股票代码和时间范围，自动分析历史暴跌事件、修复规律、原因分类，生成交互式 HTML 分析报告。

> 本工具适用于 WorkBuddy AI Agent、Claude Code、Cursor 等 AI 编程助手，也可独立作为 Python CLI 工具使用。

## 前置要求

- **Python 3.9+**
- **数据源（二选一）**
  - **WorkBuddy 用户**：已安装 WorkBuddy，无需额外配置（自动探测 westock-data）
  - **独立使用**：`pip install yfinance`（从 Yahoo Finance 获取数据）

## 安装

### 方式一：作为 WorkBuddy Skill 安装（推荐）

```bash
# 下载 skill 到 WorkBuddy skills 目录
cd ~/.workbuddy/skills/
git clone https://github.com/HelloBojack/analyze_crashes_skill.git stock-crash-analyzer
```

### 方式二：作为独立 CLI 工具安装

```bash
git clone https://github.com/HelloBojack/analyze_crashes_skill.git
cd analyze_crashes_skill
pip install -r requirements.txt
```

## 使用方法

### 基本用法

```bash
python scripts/analyze_crashes.py \
  --stock AAPL \
  --benchmark QQQ \
  --start 2021-01-01 \
  --end 2026-06-26 \
  --threshold 2.0 \
  --output report.html
```

### 参数说明

| 参数 | 说明 | 默认值 | 必填 |
|------|------|--------|------|
| `--stock` | 目标股票代码（如 AAPL, TSLA, NVDA） | - | 是 |
| `--benchmark` | 对比指数（如 QQQ, SPY, IXIC） | QQQ | 否 |
| `--start` | 开始日期（YYYY-MM-DD） | - | 是 |
| `--end` | 结束日期（YYYY-MM-DD） | - | 是 |
| `--threshold` | 暴跌阈值（百分比） | 2.0 | 否 |
| `--output` | 输出 HTML 文件路径 | - | 是 |
| `--events` | 外部事件 JSON 文件路径（可选） | - | 否 |

### 阈值建议

| 股票类型 | 推荐阈值 | 理由 |
|----------|----------|------|
| 大盘股科技（AAPL, MSFT） | 2.0% | 波动适中 |
| 高波动科技（TSLA, NVDA） | 3.0-4.0% | 日常波动较大 |
| 低波动（JNJ, PG） | 1.5% | 波动较小 |
| A 股 | 2.0-3.0% | 熔断敏感性较高 |

### 补充事件数据（可选）

创建 JSON 文件为暴跌事件添加具体原因描述：

```json
{
  "2025-03-11": "Bloomberg reports Apple delays Siri AI upgrade",
  "2026-06-25": "Apple announces product price increases across all lines"
}
```

使用时传入 `--events events.json`。

## 分析内容

### 报告模块

| 模块 | 说明 |
|------|------|
| **概览统计** | 暴跌次数、中位数修复天数、V 型修复率、自身因素次数 |
| **原因分布** | 圆环图展示三类原因占比（自身导致 / 整体下挫 / 整体偏空+自身弱） |
| **修复概率** | 2/3/5/7/10/30/60 天内修复概率，按原因分类 |
| **原因分类统计** | 每类原因的中位数、分位数、最快/最慢修复天数 |
| **跌幅分层** | 按 2-3%/3-4%/4-5%/>5% 分层分析修复难度 |
| **月度分布** | 识别暴跌季节性规律 |
| **投资关键洞察** | 暴跌后 5 天平均收益、收红概率、修复日反弹幅度、自身 vs 市场修复差距 |
| **暴跌事件列表** | 全部暴跌事件，带筛选、排序、多选原因筛选 |
| **大跌后 5 天** | 每次暴跌后第 1~5 天的涨跌情况 |
| **大跌后大涨** | 每次暴跌后首次 > 2% 大涨的时间、幅度 |

### 原因分类逻辑

根据对比指数（如 QQQ）当天表现自动分类：

| 原因 | 对比指数条件 | 含义 |
|------|-------------|------|
| **自身导致** | >= -0.3% | 大盘平稳或上涨，股票独自下跌 |
| **整体下挫** | < -1.5% | 大盘同步暴跌，市场恐慌 |
| **整体偏空+自身弱** | -1.5% ~ -0.3% | 大盘偏弱，股票跌更多 |

### 统计指标

- **中位数修复天数**：比平均值更稳健，不受极值影响
- **分位数**：25%（较快修复）、75%（较慢修复）、90%（绝大多数修复）
- **V 型修复率**：5 天内修复的比例
- **修复概率**：多时间窗口（2/3/5/7/10/30/60 天）

## 报告特性

- 左侧固定导航栏，点击平滑跳转
- 交互式 SVG 图表（零外部依赖，不依赖 CDN）
- 表格支持：关键词搜索、原因多选 checkbox 筛选、年份筛选、列排序
- Apple Design 配色（红/绿/蓝）
- 响应式布局，支持移动端

## 环境变量配置

| 环境变量 | 说明 | 示例 |
|----------|------|------|
| `WESTOCK_DATA_SCRIPT` | westock-data 脚本路径 | `/Applications/WorkBuddy.app/.../index.js` |
| `NODE_PATH` | Node.js 可执行文件路径 | `/usr/local/bin/node` |

## 数据说明

- 数据源优先使用 westock-data（WorkBuddy 内置），fallback 使用 Yahoo Finance（yfinance）
- 修复天数定义：收盘价重新超过暴跌前一日收盘价所需交易日数
- 未修复：在数据范围内仍未回到暴跌前水平
- 本报告仅供分析参考，不构成投资建议

## 目录结构

```
stock-crash-analyzer/
├── SKILL.md                          # Skill 使用说明
├── README.md                         # 本文件
├── requirements.txt                  # Python 依赖
├── scripts/
│   └── analyze_crashes.py           # 核心分析脚本
└── references/
    └── methodology.md                # 分析方法论
```

## 许可证

[MIT License](./LICENSE)
