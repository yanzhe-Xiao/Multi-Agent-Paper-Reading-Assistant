阶段 1：先把“论文输入 -> 文本输出”打通

这是最先该做的地方。

很多人一上来写 agent，最后死在 PDF 解析。
所以你第一步应该只做：论文预处理管道。

目标

把 PDF 变成可供后续 Agent 使用的结构化文本。

你要做的事
1. 文件上传

先支持单个 PDF 上传。

2. PDF 解析

提取：

标题
作者
摘要
正文
章节标题
参考文献区域
3. 文本切块

不是简单按字数切，而是尽量按：

section
subsection
段落
来切。
4. 中间结果保存

把解析后的结果存成 json。

例如：

raw_text
abstract
sections
formula_related_chunks
reference_chunks
这一阶段不要做什么
不要做 LangGraph
不要做多 Agent
不要做前端美化
不要做问答
你这阶段的成果应该是

给一个 PDF，你能打印出类似：

标题是什么
摘要是什么
有哪些章节
方法章节是哪几段
实验章节是哪几段
阶段 1 完成标准

你输入一篇经典论文 PDF，程序能稳定输出一个解析后的 JSON 文件。



# 存在的问题

针对 MinerU 将大图切分为多个小图块的问题，我计划设计一个 Figure Reconstruction 后处理流程。

## 目标

将同一张 figure 被切碎后产生的多个 img_path 重新归并为一个逻辑上的完整 figure，减少 Markdown 中的图片碎片和重复文本。

## 基本思路
遍历 MinerU 输出的 JSON 条目，重点关注 image 类型节点中的 img_path、bbox、page_idx，以及带有 image_caption 的 figure 节点。
以带 caption 的 figure 作为一个结束锚点。
从当前 figure 向前定位，找到自上一个 figure 之后出现的第一个相关 img_path。
将这一区间内连续出现的所有的字段都视为同一张大图被切分后的子图块。注意：这里不仅仅包含 image 类型的节点，还可能包含一些 OCR 文本节点，这些文本可能是图中的标签、注释等。
对这些子图块的 bbox 求并集，得到该 figure 在页面上的整体区域。
基于合并后的区域生成一个新的“大图”表示，并替换 Markdown 中原来多个碎片化的小图引用。
同时删除或折叠这些碎图导致的重复 OCR 文本和冗余描述，使最终 Markdown 更干净、更接近原始论文版面