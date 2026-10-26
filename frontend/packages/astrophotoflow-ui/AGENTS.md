# 私有 UI 包开发约定

- 先读 README、根模块导航和任务所属模块说明；只读取相关契约与测试。
- 原生应用仅通过包导出使用本包；本包不能导入 frontend/src、@/ 别名、原生 Store 或画布单例。
- 画布与宿主协调由 frontend/src/platform/astrophotoflow 桥接；共用原生 Vue/Pinia，不再创建应用。
- 本轮迁移保留既有组件逻辑、测试环境和业务断言，不以迁移为由重写样式、交互或类型体系。新增代码遵循适用前端规范。
- 内部测试通过 @ui 指向 src，生产消费使用 @astrophotoflow/ui 公开入口。
- 测试：根 pnpm test；类型检查：根 pnpm typecheck；依赖边界：见模块导航。
