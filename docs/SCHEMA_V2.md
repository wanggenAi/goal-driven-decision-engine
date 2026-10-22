# JSON 2.0 数据契约

`gqde validate FILE` 对模型与全部候选执行同一套校验；失败退出 2，输出具体错误，成功退出 0。契约由 `src/gqde/model.py` 实际执行，不依赖第三方 JSON Schema 库。2.0 各层拒绝未知字段，避免拼写错误静默生效。JSON 加载还拒绝重复键及 NaN/Infinity。

完整可运行配置见 `examples/business.json` 和 `examples/content.json`。

| 顶层字段 | 必需内容 |
| --- | --- |
| schema_version | 固定 `2.0` |
| model_version | 非空人工管理版本；参数、公式或目标改变应升级 |
| as_of | 带时区的 ISO 时间；固定评价时点、当时可用证据截止时间 |
| goal | id、description、success_measure、evaluation_window、direction、object、context、outcome_unit；target 方向额外要求数值 target |
| questions | 非空列表；每项 id、goal_id、question、metrics（唯一指标 ID 列表） |
| inputs | 输入名到 `{unit, description, min?, max?}` 的映射；输入名是表达式标识符 |
| dimensions | 每项 id、weight、weight_basis、metrics（非空） |
| gates | 列表，可为空；每项 id、metric、op、value、explanation |
| decision | `{min_score}`，范围 0–100 |
| candidates | 非空列表；每项 id、observations（必须恰好包含声明的输入） |
| validation | baseline_metric、top_k（正整数）、min_samples（至少 3 的整数） |

所有 ID/描述必须非空，维度、指标、问题、规则、候选各自 ID 唯一。每个问题只能引用本目标和已存在指标；每个指标必须被问题引用，表达式变量必须与其 inputs 精确一致；全部顶层 inputs 必须有指标使用。

## 指标

每个 metric 必须包含：

```json
{
  "id": "unit_profit",
  "expression": "price - cost - fees",
  "inputs": ["price", "cost", "fees"],
  "unit": "CNY/unit",
  "direction": "higher",
  "normalize": {"method": "min_max", "low": 0, "high": 50, "basis": "Explicit illustrative anchors"},
  "weight": 1,
  "weight_basis": "Explicit stakeholder judgment",
  "explanation": "Contribution margin per unit",
  "evidence_requirements": {
    "allowed_kinds": ["observed", "estimated", "synthetic"],
    "independently_verified": false,
    "max_age_hours": 72,
    "window_required": true
  }
}
```

- `min_max` 使用 low < high 的有限锚点；direction 为 higher / lower。
- `target` 使用 `{method, target, tolerance, basis}`，tolerance > 0，direction 必须 target。
- 权重有限且非负，每个层级总和必须正；零权重用于明确排除贡献，指标仍接受证据校验和门槛检查。正比例权重自动转换为占比。旧版 1.0 仍要求所有权重大于零。
- 表达式只支持数值常量、输入名称、括号、单目 +/-、四则运算；禁用 eval、函数、属性、索引、幂、条件与比较。表达式长不超过 256，嵌套深度不超过 24。除零与非有限结果拒绝。

## 观测

```json
{
  "value": 70,
  "unit": "CNY/unit",
  "source": "synthetic:business:fixture-v1",
  "observed_at": "2026-10-22T09:00:00+08:00",
  "kind": "synthetic",
  "independently_verified": false,
  "observation_window": {"start": "2026-09-22T00:00:00+08:00", "end": "2026-10-22T00:00:00+08:00"}
}
```

value 必须是有限数字，不接受 bool 或数字字符串。unit 与 inputs 中声明的标签精确匹配；**没有隐式货币/单位转换，也不自动推导表达式量纲**。指标输出单位由模型作者负责核验。可用 inputs.min/max 拒绝负计数、不合理比率等业务异常；跨变量关系可用指标门槛表达。

observed_at 指该数值在本次证据版本中被观测且可用的时间，必须不晚于 as_of。observation_window 是被测现象的区间，start < end <= observed_at。相同输入在不同候选的窗口必须相同（按时间点比较，允许等价时区写法）；不同输入可以来自不同窗口，例如最近期与前一期。对象/人口/预算可比性由 goal.context 与测量流程保证，系统无法自动证明。

kind 为 observed / estimated / synthetic；synthetic 禁止宣称 independently_verified=true。所有验证状态均为外部声明。超过 max_age_hours、不在 allowed_kinds、违反强制独立验证要求都会 BLOCKED；缺少必需窗口则拒绝输入。

## 结果窗口与历史协议

goal.direction 为 maximize / minimize / target，evaluation_window 是**未来实际结果**的固定区间，start >= as_of。success_measure 是操作化结果名称，outcome_unit 是真实结果单位，不是综合分数单位。

`snapshot` 保存原始 document、完整 report、engine_version、可选 predictions 和 snapshot_id。预测文件是列表，每项必须包含 candidate_id、value、unit、method、baseline_value、baseline_basis；单位必须等于 outcome_unit，窗口与对象继承快照，不提供默认预测。baseline_value 必须在决策时按历史信息确定，禁止用本次实际结果拟合。

`history SNAPSHOT OUTCOMES` 的结果输入包含 schema_version=`1.0`、snapshot_id、as_of、success_measure、outcomes；每项 `{candidate_id, observation}`。结果 observation 的 unit、window 必须匹配目标，观测时间不早于窗口结束，不晚于验证 as_of；kind 只能 observed 或 synthetic，同批不混合。synthetic 结果只能演示工作流。

摘要用于检测内容变化，不是数字签名或可信时间戳。文件独占创建避免误覆盖，但不能阻止持有者重造快照或谎报历史可用时间。真实试验应在决策前将快照提交版本控制/可信存档，保留原始证据和审计记录。
