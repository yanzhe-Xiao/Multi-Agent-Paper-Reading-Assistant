# Phase 1:

先不实现多智能体，先实现单智能体的论文阅读功能。我希望你的在实现大模型的时候使用create_agent方法创建一个agent。因为后面我需要让agent调用工具。
实现要求是使用最新的langchain 1.0版本和langgraph技术。先实现如下要求
需求如下：
  - 首先我们的论文已经在解析出来了，放在`../../docs/docs_parser`目录下。这个目录里包含了每个论文的解析结果。可以先选中其中的一个文件夹内作为测试。就以docs\docs_parser\4ffc67ef-8d72-40f9-ba82-23d39052c3db为例。其内部有效的json为docs\docs_parser\4ffc67ef-8d72-40f9-ba82-23d39052c3db\cc90a819-7d1b-4438-a96f-a20017bb84e8_content_list_optimized.json和md为docs\docs_parser\4ffc67ef-8d72-40f9-ba82-23d39052c3db\full_optimized.md。需要创建一个agent作为阅读助手，首先需要把md的内容切割后分块发给agent并让他系统的总结出内容的主要内容。这里涉及prompt的规范书写。
  - 需要对json里的图片进行映射，需要将figure N和他的路径映射起来。比如`{
    "type": "image",
    "img_path": "images/1ca4ceface65294498399a9e23ba561ae9cd13c8b6d1e3fe9ee9011f3d44d24c.jpg",
    "image_caption": [
      "Fig. 1. A robot vacuum needs to build a global occupancy map before it performs the cleaning service. However, it is unable to use coarse representations (e.g., coarse-grid maps or hand-drawn maps) of the environments. In this work, we develop CMN, which can use different coarse maps for robot navigation. Note that the size of a coarse-grid map is much smaller than that of a metric map (i.e., $20 \\times 25$ vs. $900 \\times 1000$ ). "
    ],
    "image_footnote": [],
    "bbox": [
      519,
      183,
      887,
      354
    ],
    "page_idx": 0
  },` 这里面就需要拿到{"fig 1":"images/1ca4ceface65294498399a9e23ba561ae9cd13c8b6d1e3fe9ee9011f3d44d24c.jpg"}但是不仅仅如此。有的一个图片下会有多个figure N，比如figure 1 和figure 2，这时候需要把这两个figure都映射到这个图片路径里。
  - 首次解析时不需要传入图片，只需要文本传给大模型，只有用户提问某某图片时才会使用工具调用，这个先放到后面实现。
  - 你要做的是应该把整个md文件拆分多个块的内容然后发给大模型，同时要写一个优秀的prompt，让大模型能够系统的总结出内容的主要内容。
