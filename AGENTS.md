# 四大维度

数字只来自本仓库命令的标准输出。不要心算门槛，不要补全缺失字段，不要把结果说成买入建议。

在仓库根目录执行：

```bash
python3 -m fourdim recommend
python3 -m fourdim analyze 600519
python3 -m fourdim analyze 贵州茅台
```

`recommend` 写出当天最多 3 只观察名单。`analyze` 解析一只股票，通过和不通过都要展示。

把标准输出作为回答正文。命令失败时，只说明失败原因，不另给股票。

这套说明给所有能执行命令的助手使用，不限于某一种模型。阈值在 `fourdim/rules.py`。用户没有要求改代码时，不要在对话里放宽门槛。
