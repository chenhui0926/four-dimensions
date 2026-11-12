---
name: four-dimensions
description: >-
  A股四大维度基本面筛查。用户要每天推荐 3 只、观察名单、解析某只股票、
  四大维度、毛利率、净资产收益率硬门槛时使用。运行 fourdim，
  原样呈现命令输出；缺数据即不通过，不编造财务数字，不把结果说成买入建议。
---

# 四大维度

数字只来自本仓库命令的标准输出。不要心算门槛，不要补全缺失字段。

在仓库根目录执行：

```bash
python -m fourdim recommend
python -m fourdim analyze 600519
python -m fourdim analyze 贵州茅台
```

`recommend` 写 `daily/当天日期.md`，并打印当天最多 3 只观察名单。`analyze` 解析一只股票，通过和不通过都要展示。

把标准输出作为回答正文。命令失败时，只说明失败原因，不另给股票。

阈值在 `fourdim/rules.py`。用户没有要求改代码时，不要在对话里放宽门槛。
