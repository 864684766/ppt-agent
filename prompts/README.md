# 提示词目录

提示词与调用代码分开维护，修改后下次运行读取；不代表运行中任务自动更新。

| 文件 | 调用方 | 状态 |
| --- | --- | --- |
| template_visual_analysis.md | integrations/templates/langchain_template_vision.py（外层读取并注入） | 当前视觉识别模块使用；真实测试入口为tests/test_template_vision.py |

该提示词定义视觉观察规则。输出字段Schema由适配器根据TemplateVisualAnalysis动态附加，避免提示词与数据模型重复维护字段定义。正式子Agent提示词后续按任务增加。
