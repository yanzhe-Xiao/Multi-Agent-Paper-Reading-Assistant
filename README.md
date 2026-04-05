多 Agent 论文精读助手需求文档
==================

**项目名称：** Multi-Agent Paper Reading Assistant  
**项目代号：** PaperMind  
**版本：** v1.0  
**文档类型：** 产品需求文档 + 技术需求说明  
**适用场景：** 简历项目 / 毕设 / AI Agent 工程实践 / 面试项目讲解

> 该需求文档由GPT-5.4生成

* * *

1\. 项目背景
========

随着大模型能力提升，单一 Agent 已经可以完成基础问答和总结任务，但在复杂任务场景下，单 Agent 往往存在以下问题：

1.  任务过于复杂，单次推理链条长，容易遗漏信息
2.  不同子任务需要不同“专业角色”处理，如元数据提取、方法总结、公式解释、参考文献梳理
3.  输出结构不稳定，可解释性弱，难以工程化扩展
4.  面对长篇论文时，容易出现上下文溢出、重点丢失、解释粒度不一致等问题


* * *

2\. 项目目标
========

```mermaid
flowchart TB

    %% ========== 输入与记忆 ==========
    U([用户提问]) --> Load[加载线程状态 / 长期偏好 / 历史摘要]
    Load --> Init[初始化本轮输入到 State]

    %% ========== 全局状态 ==========
    State[(PaperAgentState<br/>messages / user_query / paper_inputs / retrieved_chunks / figure_map / tool_results / review_notes / draft_answer / quality_score / user_preferences / iteration_count / final_answer)]

    Init --> Planner
    State -.读写.-> Planner

    %% ========== 主 Agent 循环 ==========
    Planner[Planner / Orchestrator Agent<br/>决定下一步动作] --> Decide{下一步做什么?}

    Decide -->|retrieve| Retrieve[检索论文 / 向量搜索]
    Decide -->|vision| Vision[读取图表 / Figure / 图片]
    Decide -->|python| Python[运行 Python 分析]
    Decide -->|web| Web[联网搜索]
    Decide -->|review| ReviewInput[构造论文分析输入]
    Decide -->|finalize| Draft[生成答案草稿]

    %% ========== 论文任务模式 ==========
    ReviewInput --> Mode{论文任务模式}
    Mode -->|单篇精读| Single[单篇论文解析]
    Mode -->|多篇对比| Multi[多篇论文对比]

    %% ========== 多 Agent 审阅层 ==========
    Single --> MultiAgent
    Multi --> MultiAgent
    Vision --> MultiAgent

    subgraph MultiAgent [多 Agent 审阅层]
        Method[方法论专家]
        Experiment[实验分析师]
        Critic[批判性审稿人]
        Consensus[意见汇总 / 共识分析]
        Method --> Consensus
        Experiment --> Consensus
        Critic --> Consensus
    end

    %% ========== 能力池 ==========
    subgraph CapabilityPool [Capability Layer]
        T1[retrieve_paper_chunks]
        T2[read_figure_by_id]
        T3[compare_papers]
        T4[run_python_stats]
        T5[search_web]
        T6[methodology_review]
        T7[experiment_review]
        T8[critical_review]
    end

    Retrieve -.调用能力.-> T1
    Vision -.调用能力.-> T2
    Multi -.调用能力.-> T3
    Python -.调用能力.-> T4
    Web -.调用能力.-> T5
    Method -.调用能力.-> T6
    Experiment -.调用能力.-> T7
    Critic -.调用能力.-> T8

    %% ========== 状态更新 ==========
    Retrieve --> Update[更新 State]
    Vision --> Update
    Python --> Update
    Web --> Update
    Consensus --> Update
    Draft --> QA

    Update --> Planner
    State -.读写.-> Update

    %% ========== 质量评估与反思 ==========
    QA[质量评估 / Reflect / Critic<br/>检查是否覆盖贡献、证据、局限、用户偏好] --> Pass{是否合格?}
    Pass -->|否：信息不足| Planner
    Pass -->|否：结构不好| Rewrite[重写草稿]
    Rewrite --> QA
    Pass -->|是| Final[输出最终答案]

    %% ========== 会话持续 ==========
    Final --> Compress{是否压缩历史?}
    Compress -->|是| Summarize[压缩历史对话为摘要<br/>保留最近2轮原始消息]
    Compress -->|否| Wait[等待下一轮提问]
    Summarize --> Wait
    Wait --> U

    %% ========== 持久化与观测 ==========
    State -.持久化.-> Memory[(Checkpointer / Store)]
    Planner -.日志/轨迹.-> Trace[(Tracing / Evaluation / LangSmith)]
    QA -.日志/分数.-> Trace
```