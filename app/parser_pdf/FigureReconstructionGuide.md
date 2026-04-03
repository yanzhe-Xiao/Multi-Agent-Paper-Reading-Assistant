# Figure Reconstruction 说明

## 先回答你的问题

不是单纯把 MinerU 切出来的小图块重新拼接起来。

当前实现的主路径是：

1. 先识别哪些碎图属于同一个 figure。
2. 对这些碎图和夹在中间的 OCR 文本求一个整体 `bbox`。
3. 优先基于原始 PDF，按这个整体区域直接裁出一张新的“大图”。

只有在 PDF 裁图不可用时，才会走降级路径：

1. 把已有的小图块按坐标贴回一个画布。
2. 把夹在中间的 OCR 文本按原位置绘制回去。

所以它本质上是“重建”，不是只做“拼接”。

## 为什么不只做拼接

如果只拼小图块，会有两个问题：

1. MinerU 有时会把图中的说明文字、标签、轨迹描述单独识别成 `text` 节点，而不是图像块。
2. 这些文字本来属于 figure 的视觉区域，只拼图片会把这部分丢掉。

因此当前实现优先直接从原始 PDF 裁整块区域。这样能同时保留：

- 图本身
- 图中的文字
- 图中的坐标轴、标注、箭头、轨迹等细节

## 输入数据依赖

当前实现使用这几类输入：

- `*_content_list.json`
- 同目录下的 `layout.json`
- 同目录下的 `*_origin.pdf`
- 同目录下的 `images/` 小图块目录

其中：

- `content_list.json` 用来识别碎图序列、caption、页码和 `bbox`
- `layout.json` 用来建立 MinerU 坐标和 PDF 坐标之间的映射
- `origin.pdf` 用来裁出最终的大图
- `images/` 用来做降级拼接

## 整体流程

### 1. 找锚点

把带 `image_caption` 的 `image` 节点当成 figure 锚点。

例如：

- `Figure 2`
- `Figure 4`
- `Figure 7`

这些带 caption 的节点通常是一个 figure 的结束位置，前面可能跟着很多无 caption 的碎图。

### 2. 回扫候选片段

从当前锚点往前找，但不是整页无脑回扫。

约束条件是：

- 必须在同一页
- 不能跨过上一个带 caption 的 figure
- 节点类型必须属于允许集合：
  - `image`
  - `text`
  - `list`
  - `equation`
  - `code`
- 候选节点必须和当前 figure 区域在空间上连续或接近

这里的“连续”主要看 `bbox` 的水平/垂直间距和重叠关系。

目的很简单：

- 把真正属于 figure 的碎片收进来
- 不把正文段落误吞进去

### 3. 判断是否真的需要重建

只有当前锚点前面确实存在“无 caption 的 image 碎片”时，才认定这是一个被切碎的大图。

如果只是普通单图，不会重建。

### 4. 合并区域

对识别出的整组片段求 `bbox` 并集，得到这个 figure 的整体区域：

```python
union_bbox = [
    min(x0),
    min(y0),
    max(x1),
    max(y1),
]
```

这一步得到的是 MinerU 坐标系下的 figure 整体边界。

### 5. 建立坐标映射

MinerU 的 `bbox` 坐标不是 PDF 的原生点坐标。

所以实现里会读取 `layout.json`，把：

- `content_list.json` 的块坐标
- `layout.json` 的块坐标

按页对齐后做线性拟合，得到：

```python
pdf_x = x_scale * mineru_x + x_offset
pdf_y = y_scale * mineru_y + y_offset
```

这样就可以把合并后的 `union_bbox` 转换为 PDF 坐标。

### 6. 主路径：直接从 PDF 裁图

这是当前默认路径，也是效果最好的路径。

实现上调用 `pdftoppm`：

1. 根据页号定位 PDF 页
2. 根据映射后的整体区域裁剪
3. 输出为新的 PNG

这样生成的新图不是由小块拼出来的，而是从原 PDF 页面直接截取的完整 figure 区域。

优点：

- 保留图中的原始文字
- 不丢图内 OCR 内容
- 不受 MinerU 切块边界影响
- 视觉效果更完整

### 7. 降级路径：碎片拼接

如果 PDF 裁图失败，或者环境里没有 `pdftoppm`，就退化到拼接方案。

做法是：

1. 创建一个以 `union_bbox` 为边界的大画布
2. 把所有 `image` 碎片按相对位置贴回去
3. 把中间的 `text` 节点按相对位置绘制回画布

这个路径只是兜底，不是主方案。

## 输出结果怎么改

重建完成后，原来的多个碎片节点会被折叠成一个新的 `image` 节点。

新节点保留原 caption，同时新增：

- 合并后的 `bbox`
- 新生成的大图 `img_path`
- `is_reconstructed_figure: true`
- `reconstruction` 元数据

`reconstruction` 里会记录：

- 原 anchor 索引
- 原碎片区间 `span`
- 原碎片 `img_path` 列表
- 夹带的 OCR 文本
- 最终采用的渲染方式

例如：

- `pdf_crop`
- `fragment_composite`

## 这次样例里识别出的重建结果

在你提供的样例中，当前实现识别并重建了 3 个 figure：

1. `Figure 2`
   对应区间 `span = [23, 55]`

2. `Figure 4`
   对应区间 `span = [133, 134]`

3. `Figure 7`
   对应区间 `span = [171, 222]`

生成的新图在：

- `docs/docs_parser/caf89a99-eccd-4042-8f87-e3912b1eb2a8/reconstructed_images/`

## 当前实现的边界

当前策略是偏保守的，目标是避免误吞正文。

所以它更适合这类模式：

- 一个 figure 被拆成很多连续碎图
- 最后一个碎片或右半部分带 caption
- 中间夹少量 OCR 文本

下面这些场景后续还可以继续增强：

1. figure 跨页
2. 图和表混排得非常近
3. 一个页面里多个 figure 非常紧邻
4. caption 不在最后一个碎片上
5. 复杂多栏排版下的误吸附

## 代码位置

核心实现：

- `app/figure_reconstruction.py`

回归测试：

- `app/test_figure_reconstruction.py`

## 一句话总结

当前方案不是简单拼接小图，而是：

先识别同一个 figure 的所有碎片和相关 OCR 区域，再优先从原始 PDF 直接裁出完整 figure；只有裁 PDF 不可用时，才回退为碎片拼接。
