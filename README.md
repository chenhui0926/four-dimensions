# 四大维度观察名单

按盈利、效率、财务健康、估值四步筛 A 股。每天早上给出最多 3 只观察名单，也可以解析一只股票。结果不是买卖建议。

## 怎么使用

先装一次：

```bash
git clone https://github.com/chenhui0926/four-dimensions.git
cd four-dimensions
python3 -m pip install -r requirements.txt
```

当天最多 3 只：

```bash
python3 -m fourdim recommend
```

解析一只股票，代码或名称都可以：

```bash
python3 -m fourdim analyze 600519
python3 -m fourdim analyze 贵州茅台
```

这两条命令就是全部用法。ChatGPT、Claude、Gemini、Copilot、Cursor、Codex 或其他能执行命令的助手，都跑它们，再把终端输出原样给你。助手不能自己编财务数字。仓库里的 `AGENTS.md` 写的是同一份要求。

也可以直接对助手说「今天推荐 3 只」或「用四大维度解析 600519」。

工作日北京时间 08:00，GitHub Action 会跑同一条 `recommend`，把结果提交到 `daily/`。东方财富有时会拒绝 GitHub 服务器的访问，那时在自己电脑上跑命令即可，规则相同。

## 规则 v1

硬门槛（缺数据就是不通过）：

- 不是 ST、退市，也不是银行、保险、证券、信托
- 最新报告期净资产收益率 ≥ 15%
- 近 5 个年报的净资产收益率每年 ≥ 12%
- 毛利率 ≥ 40%；钢铁、煤炭、化工、航运这类周期行业改为不低于行业 60 分位
- 净利润为正，经营现金流为正，且经营现金流 ≥ 净利润的 0.8 倍
- 资产负债率 < 60%
- 总市值 ≥ 50 亿

三条否决：杠杆堆出来的高净资产收益率、扣非与归母相差超过 20%、市盈率低于 15 或市净率低于 1 且营收和净利润同比都为负。

每天的 3 只只在质量通过、市盈率大于 0 且不超过 40 倍的公司里，按市盈率从低到高挑选。同一行业留 1 只。近 10 次名单里出现过的代码先跳过；不够 3 只时再放宽。

全市场批量数据只有最新报告期。5 年年报和扣非净利润只复核排序靠前的约 40 只。

## 输出

`python3 -m fourdim recommend` 把当天名单写到 `daily/YYYY-MM-DD.md`，并记入 `data/picks.json`，用来避开重复推荐。

`python3 -m fourdim analyze 贵州茅台` 只打印这一只的卡片。同行分位要先有一次 `recommend` 留下的缓存。

市场有风险。这是基本面筛查，不是买卖建议。
