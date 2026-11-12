---
name: four-dimensions
description: >-
  A股四大维度基本面筛查。用户要每天推荐 3 只、观察名单、解析某只股票、
  四大维度、毛利率、净资产收益率硬门槛时使用。运行 fourdim，
  原样呈现命令输出；缺数据即不通过，不编造财务数字，不把结果说成买入建议。
---

# 四大维度

按仓库根目录的 `AGENTS.md` 执行。命令是：

```bash
python3 -m fourdim recommend
python3 -m fourdim analyze 600519
```

任何模型都用这两条命令。不要改门槛，不要编造财务数字。
