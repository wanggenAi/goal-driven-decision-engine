# 1.0 → 2.0

0.2.0 保留 `score_document` 和原有 `score / validate / evaluate` 命令。`examples/candidates.json` 的 1.0 结果结构、状态和严格正权重约定继续支持。修复两项数值缺陷：门槛比较使用未经四舍五入的指标；归一化/聚合/误差统计避免可避免的溢出并拒绝非有限值。

旧版 `max_age_hours` 仅触发 NEEDS_EVIDENCE，旧版 observed 无独立验证字段也可能 ELIGIBLE；这只是兼容行为，不满足新版严格证据契约。旧 CSV 仅进行数值误差计算，不验证单位、来源和时间，不可当作完整历史验证。敏感性、反事实与快照明确要求 2.0，不做暗中转换。

迁移步骤：

1. schema_version 改为 2.0，指定 model_version。
2. goal 增加对象、场景、方向、结果单位和固定未来结果窗口；保留可观测 success_measure。
3. 增加 questions，逐项映射 goal_id 和 metric IDs；不允许孤立指标。
4. 建立 inputs 单位/范围契约，指标显式列出输入、单位、方向、解释、权重依据与证据要求。
5. normalize.direction 移至 metric.direction；normalize 增加 method=`min_max` 与 basis，保留 low/high。目标型改用 target/tolerance。
6. dimensions 增加 weight_basis；gates 增加独立 id 与 explanation。
7. observations 补充 unit、independently_verified，适用时补 observation_window。缺失元数据必须回查来源，不能自动伪造。synthetic 保持 synthetic。
8. 增加 validation 的事前基线、Top-K 和最小样本要求。运行 validate，再保存 snapshot。

没有自动迁移脚本：旧数据不能推断真实单位、问题、验证状态、目标窗口或参数依据。两个 2.0 示例可用作手工迁移参考。

快照记录 engine_version；当前只重放 0.2.0。未来改变计算语义时必须保留旧实现或使用记录的旧发布版本重放，不能用新公式静默覆盖历史结果。
