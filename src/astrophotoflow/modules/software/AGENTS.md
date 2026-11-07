# 软件模块约束

- 本模块拥有固定软件包、安装/就绪状态与实际调用观察；节点定义归 nodes，图/队列/执行历史归 ComfyUI，已检查结果归 data，跨模块装配归 `interfaces/application`。
- Bundle 维护与热加载按需求执行；记录准确的 Bundle 与软件版本；只做开发构建与发布目录快照，不从裸 checkout 运行。
- 进程退出不等于节点结果就绪；未知结果先查询，不自动重放；取消受理、观测到进程停止与未知结果是不同事实。
- 安装状态原子替换遵循 Windows 重试上限；进度写入失败只记日志并保留上次进度；最终状态写入失败要返回可核对的错误。
- 测试位置 `tests/modules/software/`；Bundle 夹具在 `tests/fixtures/bundles/`，真实 Siril 只在集成测试中运行。
