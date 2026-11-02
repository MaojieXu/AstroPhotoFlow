# 私有 UI 包开发约定

- 先读 README、根模块导航和任务所属模块说明；只读取相关契约与测试。
- 原生应用仅通过包导出使用本包；本包不能导入 frontend/src、@/ 别名、原生 Store 或画布单例。
- 画布与宿主协调由 frontend/src/platform/astrophotoflow 桥接；共用原生 Vue/Pinia，不再创建应用。
- 保留有效业务断言和视觉体系；现代化按[文件计划](../../../docs/development/file-refactoring-plan.md#frontend)接入生成契约和Vue Query，不维护重复类型或万能上下文。新增代码遵循适用前端规范。
- 内部测试通过 @ui 指向 src，生产消费使用 @astrophotoflow/ui 公开入口。
- 测试：根 pnpm test；类型检查：根 pnpm typecheck；依赖边界：见模块导航。
