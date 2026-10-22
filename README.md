# Goal-Driven Decision Engine (GQDE)

目标驱动、证据优先、领域无关的决策支持框架。Python 3.10+，运行时仅使用标准库，无数据库、付费 API 或自动执行交易。

**目标 → 问题 → 维度 → 指标 → 原始观测 → 综合评价 → 独立硬约束 → 行动建议 → 实际结果 → 模型检验。**

综合评分是偏好聚合值，不是未来收益预测，也不是成功概率。权重、归一化锚点和证据验证状态都有明确记录；系统不会自动声称权重最优或模型有效。

## 运行

```sh
python -m pip install -e .
python -m unittest discover -s tests -v

gqde validate examples/business.json
gqde score examples/business.json --sensitivity --output business.report.json
gqde score examples/business.json --sensitivity --format markdown --output business.report.md
gqde sensitivity examples/business.json --delta 0.05
gqde what-if examples/business.json examples/business_changes.json

gqde snapshot examples/business.json --predictions examples/business_predictions.json --output business.snapshot.json
gqde history business.snapshot.json examples/business_outcomes.json

# 相同内核运行两个领域，输出 JSON、Markdown、快照、验证及反事实结果；目录必须尚不存在。
python examples/run_examples.py --output-dir /tmp/gqde-example-run
```

无需安装也可以运行：`PYTHONPATH=src python -m gqde.cli ...`。已有命令 `score/validate examples/candidates.json`、`evaluate examples/outcomes.csv` 继续支持。

**所有 examples 数据（含预测和后续结果）均为 synthetic。未来日期仅用于演示流程，不是已经发生的经营记录。**

## 已实现的能力

- 版本化 JSON 2.0 契约：目标的可观测成功定义、对象、场景、方向与结果窗口；Goal → Question → Metric 完整引用校验，拒绝孤立指标。
- 指标的安全算术表达式、明确输入、单位、方向、权重与依据、归一化与依据、解释及证据要求。
- 观测的数值、单位、来源、观测/可用时间、类型、独立验证声明与可选观察窗口。拒绝缺失、未来观测、异常数值、单位不符和不可比窗口；不填零。
- 固定锚点 Min-Max、反向指标、对称目标距离归一化；层次加权、实际权重占比及逐项贡献。
- 独立数值规则、最大数据时效、允许证据类型、强制独立验证。违反硬约束的对象始终 BLOCKED，不参与可行排序。
- 确定性的有效权重扰动、排名变化、并列处理、第一名稳定性、排名区间和敏感指标；反事实输入/局部权重分析重新执行全部校验与门槛。
- JSON / Markdown 报告解释得分、证据、最大贡献维度、加权短板、硬约束、建议与不确定性。
- 冻结模型/公式/证据/版本/当时结果/可选数值预测的 SHA-256 快照；独占创建文件、摘要与重放验证。
- 同单位、同目标、同窗口的后续结果：预测 MAE/RMSE/bias、含并列的 Spearman、Top-K 与预先声明的简单基线比较。明确报告覆盖率、样本不足和 synthetic 限制。

## 决策状态

| 状态 | 含义 |
| --- | --- |
| BLOCKED | 硬约束或证据要求失败；评分无法抵消 |
| NEEDS_EVIDENCE | synthetic、估计、未独立验证或被截断的指标，需要审查 |
| ELIGIBLE | 通过硬约束和证据审查声明且达到阈值；建议有限试点，不保证成功 |
| BELOW_THRESHOLD | 证据声明满足要求，但低于阈值 |

可行排名包含通过硬约束的 NEEDS_EVIDENCE / BELOW_THRESHOLD 对象，供分析比较；投入资源前还要看状态。并列共享名次，ID 仅用于稳定显示。证据验证布尔值是提供者声明，系统不能证明来源真实。

## 工程与方法说明

| 模块 | 职责 |
| --- | --- |
| `src/gqde/engine.py` | 安全算术、公共校验与兼容 1.0 入口 |
| `src/gqde/model.py` | 2.0 契约、GQM、归一化、贡献、证据及硬约束 |
| `src/gqde/analysis.py` | 敏感性、排名及反事实 |
| `src/gqde/history.py` | 快照、时间隔离、实际结果、统计和基线 |
| `src/gqde/reporting.py` / `cli.py` | Markdown 与命令行 |

[完整契约](docs/SCHEMA_V2.md) · [方法与参考文献](docs/METHODOLOGY.md) · [兼容与迁移](docs/MIGRATION.md) · [实际执行示例](docs/EXAMPLE_RUN.md) · [验收记录](docs/ACCEPTANCE.md)

采用 GQM、OECD/JRC、MCDA、测量过程及 DMN 规则分离的相关思想；没有标准认证，也不是完整 DMN/FEEL 实现。没有自动学习、概率校准、数据抓取、前端或自动业务执行。
