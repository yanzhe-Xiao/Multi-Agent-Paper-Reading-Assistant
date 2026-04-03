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

为解决这些问题，本项目设计一个**基于 Supervisor 模式的多 Agent 协作系统**。系统允许用户上传论文 PDF，由总控 Agent 负责任务分发与流程调度，多个专家 Agent 分工协作，最终产出结构化的论文精读报告。

* * *

2\. 项目目标
========

本项目的目标是构建一个可演示、可扩展、可写进简历的多 Agent 论文精读系统，能够完成以下核心能力：

*   支持上传学术论文 PDF
*   自动解析论文基础信息
*   对论文核心方法进行总结
*   对关键公式和理论进行通俗解释
*   提取实验设置、结果和结论
*   梳理参考文献和相关工作
*   通过 Supervisor 调度多个专家 Agent 协同完成任务
*   输出统一格式的结构化精读报告
*   支持用户追问和定向深入分析

* * *

3\. 项目定位
========

3.1 用户定位
--------

目标用户包括：

*   求职中的 AI / LLM / Agent 工程方向学生
*   需要快速阅读论文的研究生
*   想做 AI Agent 项目积累作品集的开发者
*   希望构建复杂协作式系统的 LangChain / LangGraph 学习者

3.2 项目定位
--------

这是一个**工程化多 Agent 系统项目**，重点不只是“把论文总结出来”，而是展示：

*   多角色分工
*   状态管理
*   工具调用
*   长文本处理
*   工作流编排
*   可观测性
*   面向复杂任务的系统设计能力

* * *

4\. 产品目标与非目标
============

4.1 产品目标
--------

1.  在上传 PDF 后 1 次任务内生成完整精读报告
2.  输出内容结构化、可读性强、适合汇报和学习
3.  多 Agent 分工明确，每个 Agent 职责单一
4.  Supervisor 能根据任务状态动态决定调用哪些 Agent
5.  支持后续扩展为辩论式多 Agent、Reviewer 模式、多论文对比模式

4.2 非目标
-------

当前版本不重点支持：

*   自动复现论文代码
*   完整 LaTeX 公式渲染编辑器
*   多论文批量管理平台
*   训练领域专用模型
*   精确学术事实验证到出版级别

* * *

5\. 核心使用场景
==========

场景 1：快速读懂论文
-----------

用户上传一篇 Transformer、RAG 或 Agent 相关论文，系统生成报告，帮助用户快速理解：

*   论文讲了什么
*   创新点是什么
*   方法怎么做
*   实验结果怎么样
*   跟已有工作有什么关系

场景 2：准备面试/组会汇报
--------------

用户需要在短时间内准备一篇论文分享，系统输出：

*   论文摘要版总结
*   方法拆解
*   公式解释
*   实验结果解读
*   演讲提纲

场景 3：针对某个部分深入分析
---------------

用户上传论文后，进一步提问：

*   第 3 节的方法到底在优化什么？
*   图 2 讲的流程是什么意思？
*   公式 5 为什么这样设计？
*   这篇论文和 BERT / GPT / RAG 有什么区别？

* * *

6\. 用户故事
========

6.1 主用户故事
---------

作为一个正在学习 AI 的学生，  
我希望上传一篇论文 PDF，  
让多个 AI Agent 自动分工合作生成一份清晰的精读报告，  
这样我就可以更快理解论文，并把这个项目写进简历中展示我的 Agent 工程能力。

6.2 子用户故事
---------

*   作为用户，我希望系统先给出论文基本信息，这样我能快速确认解析是否正确
*   作为用户，我希望系统总结核心方法，而不是只复述摘要
*   作为用户，我希望系统能解释公式，最好是“通俗版解释”
*   作为用户，我希望实验结果也被提取和说明
*   作为用户，我希望最终输出是有章节结构的，而不是杂乱段落
*   作为用户，我希望可以追问某一个点，得到更深入说明
*   作为开发者，我希望系统具备日志和状态追踪能力，方便调试多 Agent 协作过程

* * *

7\. 功能需求
========

* * *

7.1 文件上传模块
----------

### 功能描述

用户上传论文 PDF，系统完成文件校验、存储、解析预处理。

### 输入

*   PDF 文件，大小限制建议 20MB 以内
*   支持单文件上传

### 输出

*   文件 ID
*   解析状态
*   原始文本块 / 页面结构 / 元信息

### 功能要求

1.  支持拖拽上传和点击上传
2.  校验文件格式必须为 PDF
3.  校验文件大小和页数上限
4.  上传成功后自动进入解析流程
5.  保存原始文件和提取后的中间结果

### 异常处理

*   非 PDF 文件提示格式错误
*   文件损坏提示解析失败
*   页数过多时提示只解析前 N 页或进入长文模式

* * *

7.2 PDF 解析模块
------------

### 功能描述

负责从 PDF 中提取：

*   标题
*   作者
*   摘要
*   正文内容
*   章节标题
*   公式上下文
*   图表说明文字
*   参考文献区域

### 功能要求

1.  按页提取文本
2.  尽可能识别章节结构
3.  将正文切分为语义 chunk
4.  为公式附近文本建立索引
5.  为参考文献单独分段保存

### 输出数据结构示例

```
{
  "paper_id": "paper_001",
  "title": "Attention Is All You Need",
  "authors": ["Ashish Vaswani", "Noam Shazeer"],
  "abstract": "...",
  "sections": [
    {"title": "Introduction", "content": "..."},
    {"title": "Method", "content": "..."}
  ],
  "formulas": [
    {"formula_id": "f1", "context": "..."}
  ],
  "references": [
    {"ref_id": "r1", "text": "..."}
  ]
}
```

* * *

7.3 Supervisor 调度模块
-------------------

### 功能描述

Supervisor 是系统总控 Agent，负责：

*   理解用户任务目标
*   决定需要调用哪些专家 Agent
*   控制调用顺序
*   汇总中间结果
*   判断是否需要补充调用某个 Agent
*   生成最终报告

### 核心职责

1.  接收用户请求和全局状态
2.  规划执行路径
3.  触发对应 Agent Tool
4.  检查子任务是否完成
5.  处理失败重试或降级
6.  输出最终整合结果

### 调度逻辑示例

*   先调用 Parse Agent 提取论文基本信息
*   再调用 Method Agent 提炼核心方法
*   若检测到论文中有较多公式，则调用 Formula Agent
*   若检测到实验章节，则调用 Experiment Agent
*   最后调用 Organizer Agent 统一输出报告

### 要求

1.  调度过程必须可追踪
2.  每次调用都要写入状态
3.  需要限制最大调用轮次，防止死循环
4.  每个 Agent 的输出必须结构化，便于整合

* * *

7.4 专家 Agent 模块
---------------

系统至少包含以下专家 Agent。

* * *

### 7.4.1 Parse Agent（解析 Agent）

#### 职责

*   识别论文标题、作者、机构、摘要、关键词
*   识别章节目录
*   输出论文基础信息

#### 输入

*   论文全文文本
*   页面结构信息

#### 输出

```
{
  "title": "...",
  "authors": ["..."],
  "abstract_summary": "...",
  "paper_type": "method/review/benchmark",
  "section_map": [...]
}
```

#### 验收要求

*   标题提取准确
*   摘要提取完整
*   能初步判断论文类型

* * *

### 7.4.2 Method Agent（方法提取 Agent）

#### 职责

*   阅读方法章节
*   总结论文核心技术路线
*   提炼创新点
*   解释模型结构或算法流程

#### 输出

```
{
  "problem_statement": "...",
  "core_idea": "...",
  "method_steps": ["...", "..."],
  "innovations": ["...", "..."],
  "model_pipeline": "..."
}
```

#### 验收要求

*   不只是复述 abstract
*   能指出“为什么这个方法有效”
*   能区分背景、方法和贡献

* * *

### 7.4.3 Formula Agent（公式讲解 Agent）

#### 职责

*   定位关键公式
*   解释公式含义
*   对变量进行说明
*   给出直观解释

#### 输出

```
{
  "key_formulas": [
    {
      "formula_desc": "...",
      "variables": {"x": "...", "y": "..."},
      "intuitive_explanation": "...",
      "why_it_matters": "..."
    }
  ]
}
```

#### 验收要求

*   至少解释论文中的 1 到 3 个关键公式
*   能输出“通俗解释”
*   避免生成无法验证的数学推导

* * *

### 7.4.4 Experiment Agent（实验分析 Agent）

#### 职责

*   提取实验设置、数据集、基线模型、指标
*   分析实验结果
*   总结论文如何验证方法有效性

#### 输出

```
{
  "datasets": ["..."],
  "baselines": ["..."],
  "metrics": ["..."],
  "main_results": "...",
  "ablation_summary": "...",
  "limitations": "..."
}
```

#### 验收要求

*   清晰说明实验目的
*   能识别主实验和消融实验
*   对结果进行解释而非简单抄表格

* * *

### 7.4.5 Reference Agent（参考文献整理 Agent）

#### 职责

*   提取参考文献列表
*   总结相关工作方向
*   找出高频引用对象
*   粗略构建“论文知识谱系”

#### 输出

```
{
  "related_topics": ["Transformer", "Seq2Seq"],
  "important_citations": ["..."],
  "possible_influences": ["..."]
}
```

#### 验收要求

*   能从参考文献中看出论文所属方向
*   能筛出代表性工作
*   不要求完全精确到 BibTeX 级别

* * *

### 7.4.6 Organizer Agent（整理 Agent）

#### 职责

*   汇总各 Agent 输出
*   统一语气和格式
*   生成最终精读报告

#### 输出

最终 Markdown / 富文本报告，包括：

1.  基本信息
2.  一句话总结
3.  背景问题
4.  核心方法
5.  关键公式解释
6.  实验结果
7.  优点与局限
8.  相关工作与参考文献
9.  适合面试/汇报时怎么讲

#### 验收要求

*   结构统一
*   逻辑通顺
*   内容不重复
*   适合直接展示

* * *

7.5 报告生成模块
----------

### 功能描述

将多 Agent 输出整合成一份精读报告。

### 输出形式

*   Markdown
*   Web 页面
*   可导出 PDF（v2 可选）

### 报告模板建议

```
# 论文精读报告

## 1. 论文基本信息
## 2. 论文要解决的问题
## 3. 核心贡献
## 4. 方法详解
## 5. 关键公式解读
## 6. 实验分析
## 7. 优势与局限
## 8. 相关工作
## 9. 一页讲清楚这篇论文
```

* * *

7.6 对话追问模块
----------

### 功能描述

支持用户在生成报告后继续追问。

### 示例问题

*   这篇论文最大的创新到底是什么？
*   第 4 个公式和损失函数的关系是什么？
*   如果让我在面试里介绍这篇论文，怎么说？
*   它和另外一篇方法相比有什么区别？

### 要求

1.  追问时可复用已有中间状态
2.  可指定问某个 Agent，例如只让 Formula Agent 深挖
3.  支持短上下文记忆

* * *

7.7 日志与可观测性模块
-------------

### 功能描述

记录多 Agent 执行轨迹，便于调试、演示和面试讲解。

### 需记录内容

*   每轮调度开始/结束
*   调用了哪个 Agent
*   输入摘要
*   输出摘要
*   耗时
*   错误信息
*   最终状态树

### 可视化建议

*   LangSmith trace
*   LangGraph state flow 图
*   前端展示时间线

* * *

8\. 非功能需求
=========

8.1 性能要求
--------

*   普通 10~20 页论文在可接受时延内完成处理
*   任务流程稳定，不应频繁中断
*   能限制 token 和工具调用次数

8.2 可扩展性
--------

*   支持增加新的专家 Agent
*   支持切换不同 LLM
*   支持替换 PDF 解析器
*   支持多论文对比模式扩展

8.3 可维护性
--------

*   每个 Agent 单独封装
*   Prompt 模板单独管理
*   状态结构统一定义
*   输出 schema 固定

8.4 可观测性
--------

*   所有关键步骤有日志
*   支持 trace 查看
*   能快速定位失败节点

8.5 安全性
-------

*   文件仅供当前用户分析
*   限制上传大小
*   不执行 PDF 内嵌脚本
*   避免将用户论文内容泄漏到公共环境

* * *

9\. 系统架构设计
==========

9.1 总体架构
--------

系统分为 5 层：

1.  **前端层**  
    文件上传、报告展示、追问交互
2.  **应用层**  
    API 服务，任务管理，报告导出
3.  **Agent 编排层**  
    Supervisor + LangGraph 状态图
4.  **能力层**  
    专家 Agent、LLM、Embedding、检索、PDF 解析
5.  **存储层**  
    文件存储、状态存储、向量数据库、日志存储

* * *

9.2 推荐技术栈
---------

### 后端

*   Python
*   FastAPI

### Agent 编排

*   LangChain
*   LangGraph

### 模型接入

*   OpenAI / Anthropic / Gemini / Qwen 任选其一

### 文档处理

*   PyMuPDF / pdfplumber / unstructured

### 向量检索

*   FAISS / Chroma

### 前端

*   Streamlit 或 Next.js

### 观测

*   LangSmith

### 存储

*   SQLite / Postgres
*   本地文件系统 / 对象存储

* * *

10\. LangGraph 状态设计
===================

10.1 全局状态建议
-----------

```
class PaperAnalysisState(TypedDict):
    user_query: str
    paper_id: str
    raw_text: str
    parsed_metadata: dict
    method_summary: dict
    formula_explanations: dict
    experiment_analysis: dict
    reference_analysis: dict
    final_report: str
    current_step: str
    invoked_agents: list
    errors: list
```

10.2 节点设计
---------

*   ingest\_pdf
*   parse\_paper
*   analyze\_method
*   explain\_formulas
*   analyze\_experiments
*   analyze\_references
*   organize\_report
*   human\_feedback
*   finish

10.3 边设计
--------

*   `ingest_pdf -> parse_paper`
*   `parse_paper -> supervisor`
*   `supervisor -> analyze_method / explain_formulas / analyze_experiments / analyze_references`
*   多个节点完成后进入 `organize_report`
*   `organize_report -> finish`

* * *

11\. Tool 设计
============

每个 Agent 封装为 Tool，供 Supervisor 调用。

示例 Tool 列表
----------

*   `extract_metadata_tool`
*   `summarize_method_tool`
*   `explain_formula_tool`
*   `analyze_experiment_tool`
*   `organize_reference_tool`
*   `compile_report_tool`

Tool 输入要求
---------

*   必须结构化
*   必须能处理部分上下文
*   需要设置超时与异常返回

* * *

12\. Prompt 设计要求
================

通用要求
----

1.  每个 Agent 的 prompt 必须角色清晰
2.  限制职责边界，避免越权
3.  输出必须 JSON 或固定模板
4.  尽量减少幻觉，强调“基于给定内容回答”

Supervisor Prompt 核心要求
----------------------

*   明确你是调度者，不直接做所有分析
*   你的任务是根据论文内容选择合适专家 Agent
*   不要重复调用无必要的 Agent
*   当已有结果足够时，进入报告整合

专家 Agent Prompt 要求
------------------

*   Parse Agent：仅处理元数据和结构
*   Method Agent：只总结方法和创新点
*   Formula Agent：只解释关键公式
*   Experiment Agent：只分析实验
*   Reference Agent：只整理参考文献
*   Organizer Agent：只负责整合

* * *

13\. 数据流设计
==========

1.  用户上传 PDF
2.  系统解析 PDF 为结构化文本
3.  Supervisor 读取用户意图和当前状态
4.  调度 Parse Agent 获取基础信息
5.  按需调用 Method / Formula / Experiment / Reference Agent
6.  中间结果写入全局状态
7.  Organizer Agent 汇总输出报告
8.  用户对报告继续追问
9.  Supervisor 根据追问再次调度相关 Agent

* * *

14\. 异常与降级策略
============

14.1 PDF 解析失败
-------------

*   提示用户重新上传
*   或只做 OCR/纯文本降级解析

14.2 公式提取失败
-----------

*   退化为解释公式上下文
*   标记“公式识别有限，仅基于周边文本解读”

14.3 超长论文
---------

*   先做章节摘要
*   再按章节调用专家 Agent
*   或只分析摘要 + 方法 + 实验章节

14.4 某个 Agent 调用失败
------------------

*   允许重试一次
*   重试失败则跳过该模块并在最终报告中注明

14.5 输出结构不合法
------------

*   进入格式修复器
*   或让该 Agent 重新生成结构化结果

* * *

15\. MVP 范围
===========

第一版只做最核心闭环。

MVP 必做
------

*   单 PDF 上传
*   Parse Agent
*   Method Agent
*   Formula Agent
*   Organizer Agent
*   Supervisor 调度
*   Markdown 报告输出
*   基础日志

MVP 可不做
-------

*   多用户系统
*   权限管理
*   导出 PDF
*   辩论机制
*   多论文比较
*   图表可视化

* * *

16\. 进阶版本规划
===========

v1.1
----

*   增加 Experiment Agent
*   增加 Reference Agent
*   支持面试讲稿模式
*   支持中英文切换输出

v1.2
----

*   增加 Reviewer Agent
*   增加 Critic Agent
*   增加“优点/缺点辩论模式”

v2.0
----

*   多篇论文对比阅读
*   自动生成 related work 对比表
*   论文知识图谱
*   与 GitHub 代码仓联动
*   生成 PPT 汇报大纲

* * *

17\. 验收标准
=========

功能验收
----

1.  用户能成功上传论文 PDF
2.  系统能调用至少 3 个 Agent 完成协作
3.  最终输出完整结构化报告
4.  用户可继续追问某一部分
5.  日志能展示 Agent 调用轨迹

质量验收
----

1.  报告结构完整
2.  输出与论文内容基本一致
3.  核心方法解释清楚
4.  公式解释有可读性
5.  Agent 输出无明显职责混乱

工程验收
----

1.  模块解耦良好
2.  状态管理清晰
3.  Prompt 管理独立
4.  可切换模型与解析器
5.  有 README 和项目架构图

* * *

18\. 推荐目录结构
===========

```
papermind/
├── app/
│   ├── api/
│   ├── agents/
│   │   ├── supervisor.py
│   │   ├── parse_agent.py
│   │   ├── method_agent.py
│   │   ├── formula_agent.py
│   │   ├── experiment_agent.py
│   │   └── organizer_agent.py
│   ├── graph/
│   │   ├── state.py
│   │   ├── nodes.py
│   │   └── edges.py
│   ├── services/
│   │   ├── pdf_parser.py
│   │   ├── chunker.py
│   │   └── report_builder.py
│   ├── prompts/
│   │   ├── supervisor.txt
│   │   ├── parse_agent.txt
│   │   ├── method_agent.txt
│   │   ├── formula_agent.txt
│   │   └── organizer_agent.txt
│   └── main.py
├── frontend/
├── data/
├── tests/
├── README.md
└── requirements.txt
```

* * *

19\. 最终交付物
==========

这个项目完整交付建议包括：

1.  可运行代码仓库
2.  README
3.  系统架构图
4.  Agent 调度流程图
5.  示例论文输入与报告输出
6.  一段演示视频

