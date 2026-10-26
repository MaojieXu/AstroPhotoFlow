# 公共基础边界

- 阅读 README、core/config.py 和受影响测试；不修改用户默认 workspace、全局 MCP 注册或已有数据。
- 不加入资产、设备、节点、运行等业务规则，不建立杂项 utils 集合。
- 除明确的 Alembic 元数据装配入口外，不导入 modules 或 interfaces。
- 保持原有配置优先级、锁、令牌、进程排空与资源定位语义。
- 历史迁移内容和 schema 0009 保持；验证命令见 README。
